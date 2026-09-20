"""Bind late-camera CPU/audio intervals to an observer-neutral game replay."""
import argparse
import csv
import json
from pathlib import Path
from tools.audit_park_instructions import parse
from tools.benchmark_report import verify_capture, sha


def audit(capture, normal, trace, spans, frame, out):
    receipt, timeline = verify_capture(capture)
    baseline, control = verify_capture(normal)
    if (timeline != control or receipt['audio_sha256'] != baseline['audio_sha256'] or
            receipt['rom_sha256'] != baseline['rom_sha256']):
        raise ValueError('Observer changed the replay')
    binding = receipt['instruction_trace']
    if binding['sha256'] != sha(trace) or receipt['span_trace']['sha256'] != sha(spans):
        raise ValueError('Unbound trace')
    with trace.open() as stream:
        rows = parse(csv.reader(stream), binding['first'], binding['last'])
    with spans.open() as stream:
        events = list(csv.reader(stream))
    camera, = [r for r in events if int(r[0]) == 8 and int(r[1]) == frame]
    end = next(i for i, r in enumerate(rows) if r['clock'] == int(camera[4]))
    start = max(i for i, r in enumerate(rows[:end]) if r['pc'] == 0xc7f293)
    before = [r for r in events if rows[start]['clock'] <= int(r[4]) <= rows[end]['clock']]
    stages = {}
    for number, name in ((0, 'nmi_entry'), (10, 'sound_driver'), (11, 'bank_restore'),
                         (5, 'packet_sender'), (8, 'camera_hook')):
        r, = [r for r in before if int(r[0]) == number]
        stages[name] = dict(frame=int(r[1]), line=int(r[2]), cycle=int(r[3]), clock=int(r[4]), pc=r[5])
    elapsed = {name: stages[b]['clock']-stages[a]['clock'] for name, a, b in (
        ('nmi_to_driver', 'nmi_entry', 'sound_driver'),
        ('sound_driver', 'sound_driver', 'bank_restore'),
        ('restore_to_sender', 'bank_restore', 'packet_sender'),
        ('sender_to_camera', 'packet_sender', 'camera_hook'))}
    # Keep all six top-level game-call intervals, including any intervening
    # interrupts. Do not charge that entire inclusive cost to actor logic.
    call_pcs = (0xc7f293, 0xc7f296, 0xc7f299, 0xc7f29c, 0xc7f29f, 0xc7f2a2)
    calls = [r for r in rows[start:end] if r['pc'] in call_pcs]
    if tuple(r['pc'] for r in calls) != call_pcs or any(r['opcode'] != 0x20 for r in calls):
        raise ValueError('Unexpected original main-call sequence')
    main_calls = [dict(caller=f'{a["pc"]:06x}', clocks=b['clock']-a['clock'],
                       start=a, end=b) for a,b in zip(calls, calls[1:]+[rows[end]])]
    window = timeline[rows[start]['frame']-1:rows[end]['frame']]
    scheduler = [dict(frame=r['frame'], armed=r['native']['deferred_game_nmi_armed'],
                      pending=r['native']['deferred_game_nmi_pending'],
                      scheduled=r['native']['deferred_game_nmi_scheduled']) for r in window]
    report = dict(frame=frame, observer_neutral=True, route_complete=receipt['capture_complete'],
        main_start=rows[start], stages=stages, elapsed_master_clocks=elapsed,
        main_call_intervals=main_calls, scheduler_frame_boundaries=scheduler,
        sources={str(p): sha(p) for p in (capture/'capture.json', normal/'capture.json',
            trace, spans, Path(__file__), Path('tools/audit_park_instructions.py'))},
        scope='Actual pre-camera stage boundaries in one exact missed-deadline sample. '
        'Sender-to-camera includes packet transfer, interrupt return and remaining game work; '
        'do not equate it to exclusive sound cost. Full timeline and PCM are neutral. '
        'Route completion is reported separately; not a speed, route or audio-fidelity pass.')
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(elapsed))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'normal', 'trace', 'spans', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--frame', type=int, required=True)
    audit(**vars(p.parse_args()))
