"""Join previously authenticated main/store intervals to actual rendered cameras.

Diagnostic only: different encounters and small CPU windows cannot certify speed.
The existing strict background-publication gate is deliberately not changed.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.audit_display_cadence import measure
from tools.benchmark_report import sha, verify_capture


def join(intervals, phases):
    displayed = {}
    for name, phase in phases.items():
        if json.loads(json.dumps(measure(phase['series']))) != json.loads(json.dumps(phase)):
            raise ValueError('Changed rendered cadence derivation')
        for row in phase['series']:
            if row['frame'] in displayed:
                raise ValueError('Overlapping rendered phases')
            displayed[row['frame']] = (name, row['camera'])
    events, excluded = [], []
    for previous, current, following in zip(intervals, intervals[1:], intervals[2:]):
        commit = current['commit']; frame = commit['frame']; camera = commit['camera']
        end = following['commit']['frame']
        if not previous['commit']['frame'] < frame < end:
            raise ValueError('Camera stores not strictly ordered')
        reason = None
        if camera == previous['commit']['camera']:
            reason = 'unchanged camera'
        elif any(f not in displayed for f in range(frame-1, end+1)):
            reason = 'outside complete rendered phase'
        elif len({displayed[f][0] for f in range(frame-1, end+1)}) != 1:
            reason = 'rendered phase boundary'
        elif displayed[frame-1][1] == camera:
            reason = 'target already visible before store'
        if reason:
            excluded.append(dict(frame=frame, reason=reason)); continue
        visible = next((f for f in range(frame, end+1) if displayed[f][1] == camera), None)
        events.append(dict(start_frame=current['start']['frame'], store_frame=frame,
            store_line=commit['line'], camera=camera, display_frame=visible,
            store_to_display=None if visible is None else visible-frame,
            start_to_display=None if visible is None else visible-current['start']['frame'],
            phase=displayed[frame][0]))
    if not events:
        raise ValueError('No changed camera stores with complete rendered coverage')
    return dict(events=events, excluded=excluded,
        boundary_intervals_not_paired=min(2, len(intervals)),
        missing_display=sum(e['display_frame'] is None for e in events),
        store_to_display=dict(Counter(e['store_to_display'] for e in events)),
        start_to_display=dict(Counter(e['start_to_display'] for e in events)))


def bound_report(path):
    report = json.loads(path.read_text())
    sources = dict(report['sources'])
    for run in report.get('runs', {}).values():
        sources.update(run['sources'])
    for name, digest in sources.items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed source: '+name)
    return report


def audit(nes_main, snes_main, nes_cadence, snes_cadence, snes_normal,
          nes_run, snes_run, out):
    main = {'nes': bound_report(nes_main), 'snes': bound_report(snes_main)}
    cadence = {'nes': bound_report(nes_cadence)['runs'][nes_run],
               'snes': bound_report(snes_cadence)['runs'][snes_run]}
    for system in ('nes', 'snes'):
        if not any(name.endswith('/capture.json') and
                   main[system]['sources'].get(name) == digest
                   for name, digest in cadence[system]['sources'].items()):
            raise ValueError('Main and renderer lack a common authenticated control')
    receipt, rows = verify_capture(snes_normal)
    if receipt['rom_sha256'] != cadence['snes']['rom_sha256']:
        raise ValueError('Different SNES ROM')
    if main['snes']['sources'].get(str(snes_normal/'capture.json')) != sha(snes_normal/'capture.json'):
        raise ValueError('Different SNES main control')
    if cadence['nes']['scenario_sha256'] != cadence['snes']['scenario_sha256']:
        raise ValueError('Different navigation policy')
    for interval in main['snes']['intervals']:
        commit = interval['commit']
        ram = bytes.fromhex(rows[commit['frame']-1]['game_ram_hex'])
        if ram[0xf6] != commit['camera_low']:
            raise ValueError('Frame-end low camera differs from store')
        prior = bytes.fromhex(rows[commit['frame']-2]['game_ram_hex'])
        if (ram[0x3d]^prior[0x3d]) & 1:
            raise ValueError('Ambiguous high camera bit within commit frame')
        commit['camera'] = commit['camera_low'] | ((ram[0x3d]&1)<<8)
    result = {system: join(main[system]['intervals'], cadence[system]['phases'])
              for system in ('nes', 'snes')}
    result.update(release_ready=False, sources={str(p): sha(p) for p in (
        Path(__file__), nes_main, snes_main, nes_cadence, snes_cadence, snes_normal/'capture.json')},
        scope='Previously authenticated exact-PC intervals joined to every rendered street line. '
              'Changes only; unchanged cameras and boundary/ambiguous cases retained separately. '
              'Frame counts are within-system, not equal-work/input-latency measurements. '
              'Different encounters and CPU windows; no full-game speed verdict or waiver of strict gates.')
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({s:{k:result[s][k] for k in ('store_to_display','start_to_display','missing_display')}
                      for s in ('nes','snes')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('nes-main','snes-main','nes-cadence','snes-cadence','snes-normal','out'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('nes-run','snes-run'):
        parser.add_argument('--'+name, required=True)
    audit(**vars(parser.parse_args()))
