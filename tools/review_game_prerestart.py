"""Current-game pre-KON review, retaining separate bootstrap latch identities."""
import argparse
import csv
import json
from pathlib import Path
import shutil

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_postpublish_keyon import load
from tools.audit_pulse_onset import parse_voice
from tools.audit_recorded_transients import waveform_svg
from tools.audit_voice_edges import parse, registers, validate_group
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.check_game_prerestart import characterize
from tools.frame_audit import verify_frame


def latch_index(events):
    # Bootstrap legitimately restarts both voices more than once before packet1.
    indexed = {(e['packet'], e['voice'], e['keyon_write']['tick']): e for e in events}
    if len(indexed) != len(events):
        raise ValueError('Duplicate actual hardware latch')
    return indexed


def review(plan_dir, normal, observed, out):
    if out.exists():
        raise ValueError('Fresh review required')
    selection = bound_report(plan_dir/'report.json')
    binding = bound_report(observed/'prerestart-capture.json')
    control = bound_report(normal/'prerestart-capture.json')
    candidate = Path(selection['candidate'])
    proof, writes, _ = load(observed, normal, candidate)
    a, ar = verify_capture(observed)
    b, br = verify_capture(normal)
    equivalent(a, ar, b, br)
    prior = json.loads((Path(selection['capture'])/'capture.json').read_text())
    for key in ('RCR_DSP_LATENCY_TRACE', 'RCR_DSP_DAC_PCM'):
        if a['dsp_latency_observer']['traces'][key]['sha256'] != prior['dsp_latency_observer']['traces'][key]['sha256']:
            raise ValueError('Selected clock/PCM population changed')
    rate, pcm = wavfile.read(observed/'audio.wav')
    if rate != 32040 or pcm.dtype != np.int16 or pcm.ndim != 2 or pcm.shape[1] != 2:
        raise ValueError('Wrong native PCM')
    rows = parse(Path(binding['trace']), selection['windows'])
    reg = registers(writes)
    reconstructed = {s: validate_group(s, r, pcm[s], reg) for s, r in rows.items()}
    with Path(binding['onset']).open() as f:
        latches = parse_voice(list(csv.reader(f)), writes)
    matched = latch_index(latches)
    result = []
    for item in selection['selected']:
        event = item['event']
        latch = matched[event['packet'], event['voice'], event['keyon']['tick']]
        result.append(dict(characterize(event, latch['tick'], reconstructed, writes),
                           selection=item['reasons']))
    # Corrupt a real selected observation; exact mixer reconstruction must fail.
    sample = next(iter(rows))
    corrupt = [dict(r) for r in rows[sample]]
    next(r for r in corrupt if r['kind'] == 'V')['amp'] += 1
    try:
        validate_group(sample, corrupt, pcm[sample], reg)
    except ValueError:
        rejected = True
    else:
        raise ValueError('Corrupt actual voice contribution survived')
    paths = [Path(__file__), Path('tests/test_prerestart_measurement.py'),
             Path('tools/check_game_prerestart.py'), Path('tools/audit_voice_edges.py'),
             Path('tools/audit_pulse_pitch.py'), Path('tools/audit_pulse_onset.py'),
             Path('tools/audit_recorded_transients.py'), Path('tools/frame_audit.py'),
             plan_dir/'report.json', observed/'prerestart-capture.json', normal/'prerestart-capture.json']
    sources = dict(selection['sources'], **binding['sources'])
    sources.update(control['sources']); sources.update(proof['sources'])
    sources.update({str(p): sha(p) for p in paths})
    report = dict(sources=sources, events=result, reconstructed_samples=len(rows),
        selected_restarts=len(result), total_restarts=selection['total_restarts'],
        nonzero_setups=sum(bool(e['nonzero_samples']) for e in result),
        split_pitch_samples=sum(e['split_pitch_samples'] for e in result),
        nonzero_split_samples=sum(e['nonzero_split_samples'] for e in result),
        full_route_observer_neutral=True, same_clock_and_pcm_as_selection=True,
        corrupted_voice_contribution_rejected=rejected,
        scope='Timing-selected current-game setup intervals, all-voice native DAC reconstruction. '
              'Nonzero pre-restart output is not itself a bug; split pitch is an intermediate '
              'value, not proof of an audible pop. Not hardware qualification or a whole-route '
              'absence claim. No ROM or audio changes.')
    out.mkdir()
    examples = []
    for voice in (0, 1):
        eligible = [e for e in result if e['voice'] == voice]
        for label, event in [('longest', max(eligible, key=lambda e: e['hardware_latch_tick']-e['first_config_tick'])),
                             ('shortest', min(eligible, key=lambda e: e['hardware_latch_tick']-e['first_config_tick']))]:
            examples.append((f'voice{voice}-{label}', event))
    cards, clips = [], []
    for name, event in examples:
        center = event['keyon_write_tick']//32
        first, last = max(0, center-8000), min(len(pcm), center+8000)
        audio = out/(name+'.wav')
        wavfile.write(audio, rate, pcm[first:last])
        rr, decoded = wavfile.read(audio)
        if rr != rate or not np.array_equal(decoded, pcm[first:last]):
            raise ValueError('Changed native excerpt')
        frame = next(r for r in ar if r['audio_start_sample'] <= center < r['audio_start_sample']+r['audio']['samples'])
        picture = verify_frame(observed, frame)
        sources[str(picture)] = sha(picture)
        shutil.copyfile(picture, out/(name+'.png'))
        clips.append(dict(name=name, first=first, last=last, frame=frame['frame'],
                          packet=event['packet'], voice=event['voice']))
        cards.append(f'<section><h2>{name}: packet {event["packet"]}</h2>'
            f'<img src="{name}.png" alt="Unmodified game frame {frame["frame"]}">'
            f'<p>{event["nonzero_samples"]} nonzero pre-latch samples; '
            f'{event["split_pitch_samples"]} split-pitch samples.</p>'
            +waveform_svg(pcm[first:last])+f'<audio controls preload="none" src="{name}.wav"></audio></section>')
    table = ''.join(f'<tr><td>{e["packet"]}</td><td>{e["voice"]}</td>'
        f'<td>{e["hardware_latch_tick"]-e["first_config_tick"]}</td>'
        f'<td>{e["nonzero_samples"]}</td><td>{e["split_pitch_samples"]}</td></tr>' for e in result)
    html = '<!doctype html><meta charset="utf-8"><title>Current-game pulse setup</title>'
    html += '<style>body{background:#101722;color:#e9eff8;font:17px system-ui;max-width:1150px;margin:32px auto} '
    html += 'a{color:#8de} .cards{display:grid;grid-template-columns:1fr 1fr;gap:20px} '
    html += 'section{background:#1d2938;padding:18px} img{width:100%;image-rendering:pixelated} '
    html += 'audio{width:100%}td,th{padding:6px 18px;border-bottom:1px solid #456}</style>'
    html += '<h1>Current-game pulse setup before restart</h1><p>Unchanged cartridge3065; 9,248 game frames. '
    html += 'Full same-core observer control and exact earlier DSP clock/PCM identity passed.</p>'
    html += f'<p>{len(result)} timing-selected restarts; {len(rows)} reconstructed all-voice DAC samples. '
    html += f'{report["nonzero_setups"]} setups have nonzero old-voice output; '
    html += f'{report["split_pitch_samples"]} split-pitch samples ({report["nonzero_split_samples"]} nonzero).</p>'
    html += '<p>Nonzero setup output is not automatically a defect. Clips are native full mix, '
    html += 'not isolated pulse stems or physical capture. No listening or pop-free claim. '
    html += 'Selection is by register timing, not waveform peaks. Longest/shortest examples per voice shown.</p>'
    html += '<div class="cards">'+''.join(cards)+'</div><h2>All selected intervals</h2>'
    html += '<table><tr><th>Packet</th><th>Voice</th><th>Setup→latch clocks</th><th>Nonzero</th><th>Split pitch</th></tr>'+table+'</table>'
    html += '<p><a href="report.json">Full trace-derived measurements and source bindings</a></p>'
    (out/'index.html').write_text(html)
    report['clips'] = clips
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('sources', 'events', 'artifacts', 'clips')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('plan-dir', 'normal', 'observed', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    review(**vars(p.parse_args()))
