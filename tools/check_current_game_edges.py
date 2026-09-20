"""Reconstruct current-game PCM discontinuities without calling normal edges pops."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_postpublish_keyon import load
from tools.audit_pulse_pitch import pitch_updates, sample_expectation
from tools.audit_voice_edges import parse, registers, validate_group
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent


def select(events, samples, radius=128):
    if not events or not isinstance(radius, int) or radius < 1:
        raise ValueError('Need measured events and positive fixed radius')
    points = sorted(e['sample'] for e in events)
    if len(points) != len(set(points)):
        raise ValueError('Duplicate selected event')
    windows = []
    for sample in points:
        a, b = sample-radius, sample+radius+1
        if a < 1 or b > samples:
            raise ValueError('Selected event lacks full context')
        if windows and a <= windows[-1][1]:
            windows[-1][1] = max(windows[-1][1], b)
        else:
            windows.append([a,b])
    if len(windows) > 64:
        raise ValueError('Observer capacity exceeded')
    return windows


def plan(review, candidate, normal, capture, out):
    if out.exists():
        raise ValueError('Fresh plan required')
    prior = bound_report(review/'report.json')
    receipt, _ = verify_capture(normal)
    if (prior['rom_sha256'] != sha(candidate/'native-cpu.sfc') or
            receipt['rom_sha256'] != prior['rom_sha256'] or
            prior['sources'].get(str(normal/'audio.wav')) != sha(normal/'audio.wav')):
        raise ValueError('Different selected cartridge or waveform')
    events = prior['audio']['strongest_separated_events']
    windows = select(events, prior['audio']['samples'])
    sources = {str(p): sha(p) for p in (Path(__file__), review/'report.json',
        normal/'capture.json', normal/'audio.wav', capture/'capture.json',
        candidate/'manifest.json', candidate/'native-cpu.sfc')}
    result = dict(candidate=str(candidate), normal=str(normal), capture=str(capture),
        review=str(review), events=events, windows=windows, sources=sources, scope=__doc__)
    out.mkdir()
    (out/'windows.txt').write_text(''.join(f'{a} {b}\n' for a,b in windows))
    result['sources'][str(out/'windows.txt')] = sha(out/'windows.txt')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(events=len(events), samples=sum(b-a for a,b in windows))))


def audit(plan_dir, normal, observed, out):
    if out.exists():
        raise ValueError('Fresh audit required')
    selection = bound_report(plan_dir/'report.json')
    binding = bound_report(observed/'prerestart-capture.json')
    if binding['plan'] != str(plan_dir) or not binding['observer_neutral']:
        raise ValueError('Wrong observation plan')
    candidate = Path(selection['candidate'])
    receipt, rows = verify_capture(observed)
    control, plain = verify_capture(normal)
    equivalent(receipt, rows, control, plain)
    if receipt['core_sha256'] != control['core_sha256']:
        raise ValueError('Different-core observation control')
    proof, writes, _ = load(observed, normal, candidate)
    old = json.loads((Path(selection['capture'])/'capture.json').read_text())
    for key in ('RCR_DSP_LATENCY_TRACE', 'RCR_DSP_DAC_PCM'):
        if receipt['dsp_latency_observer']['traces'][key]['sha256'] != old['dsp_latency_observer']['traces'][key]['sha256']:
            raise ValueError('Selected DSP execution changed')
    rate, pcm = wavfile.read(normal/'audio.wav')
    if rate != 32040 or pcm.dtype != np.int16 or pcm.ndim != 2 or pcm.shape[1] != 2:
        raise ValueError('Wrong native audio')
    groups = parse(Path(binding['trace']), selection['windows'])
    reg = registers(writes)
    validated = {s: validate_group(s, r, pcm[s], reg) for s,r in sorted(groups.items())}
    updates = [pitch_updates(writes,v) for v in (0,1)]
    tables = [([u['low']['tick'] for u in us], [u['high']['tick'] for u in us],
               [u['low']['value'] for u in us], [u['high']['value'] for u in us]) for us in updates]
    split = []
    for sample, group in validated.items():
        previous = validated.get(sample-1)
        if previous and previous['noise']['after'] != group['noise']['before']:
            raise ValueError('Noise history discontinuity')
        for voice in (0,1):
            source = group['sources'][voice]
            if reg(0x2d,32*sample-4) & (1 << voice):
                raise ValueError('Pitch modulation outside oracle')
            expected = sample_expectation(source['tick']+1, voice, source['previous_delay'], updates[voice], *tables[voice])
            if source['pitch'] != expected['expected']:
                raise ValueError('Unexplained pitch latch')
            if expected['split_byte']:
                split.append(dict(sample=sample,voice=voice,output=source['output'],**expected))
    events = []
    for event in selection['events']:
        sample,ch = event['sample'],event['channel']
        a,b = validated[sample-1],validated[sample]
        if (int(pcm[sample-1,ch]),int(pcm[sample,ch])) != (event['before'],event['after']):
            raise ValueError('Selected sample changed')
        voices = []
        for voice in range(8):
            x,y = a['sources'][voice],b['sources'][voice]
            fields = ('env','non','pitch','regpitch','delay','srcn','adsr','gain','flg')
            voices.append(dict(voice=voice, amplitude_before=a['amplitudes'][voice,ch],
                amplitude_after=b['amplitudes'][voice,ch],
                amplitude_delta=b['amplitudes'][voice,ch]-a['amplitudes'][voice,ch],
                volume_before=a['voices'][voice,ch]['volume'], volume_after=b['voices'][voice,ch]['volume'],
                source_before=x,source_after=y,changed_controls=[key for key in fields if x[key]!=y[key]]))
        events.append(dict(selected=event,noise_before=a['noise'],noise_after=b['noise'], voices=voices,
            master_before=a['mixes'][ch],master_after=b['mixes'][ch],
            nearby_dsp_writes=[w for w in writes if 32*(sample-6) <= w['tick'] <= 32*(sample+6)],
            nearby_split_pitch=[s for s in split if abs(s['sample']-sample)<=128]))
    sample = selection['events'][0]['sample']
    controls = {}
    for name,kind,field in (('noise','N','after'),('envelope','S','env'),('volume','V','volume'),('mix','M','output')):
        changed = [r.copy() for r in groups[sample]]
        target = next(r for r in changed if r['kind']==kind and (kind!='S' or r['voice']==3))
        target[field] ^= 1
        try:
            validate_group(sample,changed,pcm[sample],reg)
        except ValueError:
            controls[name] = True
        else:
            controls[name] = False
    if not all(controls.values()):
        raise ValueError('Failed mutation control')
    sources = {**selection['sources'], **binding['sources'], **proof['sources']}
    paths = [Path(__file__), Path('tools/check_game_prerestart.py'), Path('tools/audit_voice_edges.py'),
             Path('tools/audit_pulse_pitch.py'), Path('tools/audit_postpublish_keyon.py'),
             plan_dir/'report.json', observed/'prerestart-capture.json', normal/'timeline.json', normal/'audio.wav']
    sources.update({str(p):sha(p) for p in paths})
    report = dict(events=events,selected_samples=len(groups),sources=sources,negative_controls=controls,
        split_pitch_samples=split,observer_neutral=True,raw_dac_matches=True,
        pop_free_verified=False,physical_attribution=False,release_ready=False,
        scope=__doc__+' Selection frozen from previous strongest-step ranking. Every selected sample '
        'reconstructed from all eight DSP voices and native mix; same-core full-route control and '
        'identical DSP write trace required. This tests the source of these emulator edges, '
        'not whether they correspond to the user\'s physical complaint. No sound filtering or ROM change.')
    out.mkdir()
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(samples=len(groups),split_pitch_samples=len(split),controls=controls,
        events=[dict(sample=e['selected']['sample'], changed=[dict(voice=v['voice'],delta=v['amplitude_delta'],
            controls=v['changed_controls'],volume=[v['volume_before'],v['volume_after']])
            for v in e['voices'] if v['amplitude_delta']],nearby_writes=e['nearby_dsp_writes']) for e in events])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command, names in [('plan', ('review','candidate','normal','capture','out')),
                           ('audit', ('plan-dir','normal','observed','out'))]:
        p = sub.add_parser(command)
        for name in names:
            p.add_argument('--'+name,type=Path,required=True)
    args = vars(parser.parse_args())
    globals()[args.pop('command')](**args)
