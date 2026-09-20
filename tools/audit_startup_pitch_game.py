"""Qualify actual compact-engine restarts and retain full-game timing differences."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import shutil

import numpy as np
from scipy.io import wavfile

from tools.analyze_audio_bus import analyze as analyze_bus
from tools.audit_main_display_latency import bound_report
from tools.audit_main_store_latency import parse
from tools.audit_ordinary_route_timing import cadence
from tools.audit_postpublish_keyon import load
from tools.audit_pulse_onset import parse_voice, characterize
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.frame_audit import verify_frame
from tools.review_startup_pitch_trial import startup_window


def note_windows(events, writes, ready):
    result, inactive = [], []
    for event in events:
        voice, packet = event['voice'], event['packet']
        configuration = [w for w in writes if w['packet'] == packet and
                         w['tick'] < ready[packet]['tick'] and
                         w['register'] in (voice*16+2, voice*16+3)]
        if not configuration:
            regs = ready[packet]['registers']
            if regs[voice*16] or regs[voice*16+1]:
                raise ValueError('Unstaged restart remains audible')
            inactive.append(dict(packet=packet, voice=voice, reason='No pitch publication; both volumes zero'))
            continue
        result.append(startup_window(event, writes, ready))
        if any(s['output'] for s in event['samples'][1:6]) or any(s['env'] for s in event['samples'][1:5]):
            raise ValueError('Actual DSP startup is not silent')
    return result, inactive


def cross_game(before, after):
    if not before or len(before) != len(after):
        raise ValueError('Different full-route frame coverage')
    changed, callbacks = [], []
    for a, b in zip(before, after):
        keys = (set(a) | set(b))-{'audio', 'audio_start_sample'}
        fields = sorted(k for k in keys if a.get(k) != b.get(k))
        if fields:
            changed.append(dict(frame=a['frame'], fields=fields))
        old = [a['audio_start_sample'], a['audio']['samples']]
        new = [b['audio_start_sample'], b['audio']['samples']]
        if old != new:
            callbacks.append(dict(frame=a['frame'], parent=old, trial=new))
    return dict(exact_nonaudio_timeline_equal=not changed, differences=changed,
        changed_field_counts=dict(Counter(k for r in changed for k in r['fields'])),
        callback_differences=callbacks, exact_callback_timeline_equal=not callbacks,
        scope='All differences retained, including CPU PC/status, stack/RAM, graphics, and waypoint state. '
              'No broad timing equivalence inferred from equal route completion.')


def audit(candidate, observed, normal, parent, parent_observed, parent_normal, state, out):
    if out.exists():
        raise ValueError('Fresh audit required')
    binding = bound_report(observed/'startup-game.json')
    state_proof = bound_report(state/'report.json')
    if not state_proof['passed']:
        raise ValueError('Failing compact state/timer qualification')
    old, oldwrites, _ = load(parent_observed, parent_normal, parent)
    new, writes, _ = load(observed, normal, candidate)
    if not old['passed']:
        raise ValueError('Parent fails its existing configuration-before-KON gate')
    receipt, rows = verify_capture(observed)
    control, plain = verify_capture(normal)
    equivalent(receipt, rows, control, plain)
    prior, priorrows = verify_capture(parent_normal)
    paths = receipt['dsp_latency_observer']['traces']
    with Path(paths['RCR_DSP_LATENCY_TRACE']['path']).open() as f:
        trace = list(csv.reader(f))
    ready, regs = {}, [0]*128
    for row in trace:
        if row[0] == 'D':
            regs[int(row[5])] = int(row[6])
        elif row[0] == 'R' and int(row[1]):
            ready[int(row[1])] = dict(tick=int(row[2]), registers=regs.copy())
    with Path(binding['onset']).open() as f:
        latches = parse_voice(list(csv.reader(f)), writes)
    onsets = characterize(latches, ready)
    windows, inactive = note_windows(onsets['events'], writes, ready)
    if not windows:
        raise ValueError('No staged gameplay restarts')
    # The old gate intentionally flags the new post-KON pitch writes. No SRCN
    # or volume write is permitted to move after KON under that exception.
    other_late = [w for e in new['events'] for w in e['changed_configuration_after_restart']
                  if w['register'] % 16 not in (2, 3)]
    if other_late:
        raise ValueError('Non-pitch configuration moved after restart')
    with Path(binding['main']).open() as f:
        loops, censored = parse(csv.reader(f), {int(k): v for k, v in binding['points'].items()},
                                len(rows), (candidate/'native-cpu.sfc').read_bytes())
    for loop in loops:
        loop['nmi_advances'] = (loop['finish']['nmi']-loop['start']['nmi']) & 65535
    timing = cadence(loops, rows)
    buses = []
    for root in (parent_observed, observed):
        r = json.loads((root/'capture.json').read_text())
        path = Path(r['dsp_latency_observer']['traces']['RCR_AUDIO_BUS_TRACE']['path'])
        with path.open() as f:
            buses.append(analyze_bus(list(csv.reader(f)), length_gate=True))
    # Preserve both exact timing/identity comparisons; command equality alone
    # must not stand in for original-speed or same-game-state equivalence.
    commands_equal = [p['bytes'] for p in buses[0]['packets']] == [p['bytes'] for p in buses[1]['packets']]
    packet_timing_equal = buses[0]['packets'] == buses[1]['packets']
    cross = cross_game(priorrows, rows)
    result = dict(rom_sha256=receipt['rom_sha256'], observer_neutral=True,
        frames=len(rows), packets=new['packets'], commands_equal=commands_equal,
        complete_packet_records_equal=packet_timing_equal,
        restarts=onsets['restarts'], eligible_restarts=onsets['eligible'],
        staged_restarts=len(windows), unstaged_muted_restarts=inactive,
        failed_startup_windows=[w for w in windows if not w['passed']],
        wrong_first_pitch=onsets['wrong_first_pitch'], stale_nonzero_onsets=onsets['stale_nonzero_onsets'],
        kon_phases=sorted({w['kon_tick'] % 64 for w in windows}), windows=windows,
        old_ordering_gate_passed=new['passed'], other_late_configuration=other_late,
        route_cadence=timing, censored_main_events=censored, cross_game=cross,
        restart_timing_passed=not any(not w['passed'] for w in windows)
            and not onsets['wrong_first_pitch'] and not onsets['stale_nonzero_onsets'],
        release_ready=False, physical_audio_verified=False,
        scope='Current-game observed DSP/received bytes/native DAC plus main-loop cadence. '
              'New gate explicitly permits only pitch writes during measured silent startup. '
              'All cross-ROM RAM/image/callback differences retained; not a full-game speed, '
              'NES-waveform, subjective-pop, or hardware pass.')
    sources = dict(binding['sources'], **state_proof['sources'])
    sources.update(old['sources']); sources.update(new['sources'])
    sources.update({str(p): sha(p) for p in (Path(__file__), Path('tests/test_startup_game.py'),
        Path('tools/audit_ordinary_route_timing.py'), Path('tools/audit_main_store_latency.py'),
        Path('tools/audit_pulse_onset.py'), Path('tools/review_startup_pitch_trial.py'),
        Path('tools/frame_audit.py'), observed/'startup-game.json', state/'report.json')})
    out.mkdir()
    cards = []
    changed_frames = [r['frame'] for r in cross['differences'] if 'video_sha256' in r['fields']]
    # All differences remain in JSON; show first four without cherry-picking.
    for frame in changed_frames[:4]:
        cards.append(f'<section><h2>Changed image: frame {frame}</h2><div class="pair">')
        for label, root, timeline in [('parent', parent_normal, priorrows), ('trial', normal, rows)]:
            path = verify_frame(root, timeline[frame-1]); sources[str(path)] = sha(path)
            name = f'frame-{frame}-{label}.png'; shutil.copyfile(path, out/name)
            cards.append(f'<figure><img src="{name}"><figcaption>{label}</figcaption></figure>')
        cards.append('</div></section>')
    clips = []
    target = next((w for w in windows if w['packet'] == 6222 and w['voice'] == 1), None)
    oldtarget = next((e for e in old['events'] if e['packet'] == 6222 and e['voice'] == 1), None)
    if commands_equal and target is not None and oldtarget is not None:
        center = oldtarget['keyon']['tick']//32
        first, last = center-64080, center+64080
        for label, root in [('parent', parent_normal), ('trial', normal)]:
            rate, pcm = wavfile.read(root/'audio.wav')
            if rate != 32040 or pcm.dtype != np.int16 or not 0 <= first < last <= len(pcm):
                raise ValueError('Invalid native target excerpt')
            wavfile.write(out/(label+'.wav'), rate, pcm[first:last])
            rr, decoded = wavfile.read(out/(label+'.wav'))
            if rr != rate or not np.array_equal(decoded, pcm[first:last]):
                raise ValueError('Changed native excerpt')
            clips.append(dict(label=label, source=str(root/'audio.wav'), first=first, last=last))
        result['packet6222'] = target
    html = '<!doctype html><meta charset="utf-8"><title>Compact startup-pitch game trial</title>'
    html += '<style>body{background:#111a26;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}'
    html += 'a{color:#8df}.pair{display:flex}figure{margin:8px;flex:1}img{width:100%;image-rendering:pixelated}audio{width:100%}</style>'
    html += '<h1>Compact pitch-staging: actual game trial</h1><p>Same SPC upload length; receiver and game code preserved. '
    html += 'Offline only. No MiSTer or OBS operation.</p>'
    html += f'<p>{len(rows):,} frames, {new["packets"]:,} received packets; command bytes equal parent: {commands_equal}. '
    html += f'{len(windows):,} staged restarts, {len(inactive)} unstaged/muted. Startup gate: {result["restart_timing_passed"]}.</p>'
    html += f'<p>Four-room cadence gate: {timing["passed"]}. Changed images: {len(changed_frames)}. '
    html += f'Other nonaudio timeline differences: {len(cross["differences"]):,} frames; '
    html += f'callback differences: {len(cross["callback_differences"]):,}. These are retained, not timing equivalence.</p>'
    if clips:
        html += '<h2>Packet6,222 context: untouched native full mix</h2><p>Same absolute sample range in both recordings; '
        html += 'no gain, resampling or phase fitting. Not a subjective pop-fix claim.</p>'
        html += '<p>Parent</p><audio controls preload="none" src="parent.wav"></audio>'
        html += '<p>Trial</p><audio controls preload="none" src="trial.wav"></audio>'
    html += '<h2>First four changed frames</h2>'+''.join(cards)
    html += '<p>Renderer, DMA, menus, combat, NES audio fidelity and physical qualification remain separate gates. '
    html += '<a href="report.json">Complete measurements, failures and source bindings</a></p>'
    (out/'index.html').write_text(html)
    result.update(sources=sources, clips=clips, artifacts={p.name: sha(p) for p in out.iterdir()})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('packets', 'commands_equal', 'complete_packet_records_equal',
        'restarts', 'staged_restarts', 'wrong_first_pitch', 'stale_nonzero_onsets', 'restart_timing_passed')}))
    print(json.dumps(dict(cadence=timing['passed'], changed_images=len(changed_frames),
                         nonaudiotimeline=len(cross['differences']), callbacks=len(cross['callback_differences']))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'observed', 'normal', 'parent', 'parent-observed', 'parent-normal', 'state', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
