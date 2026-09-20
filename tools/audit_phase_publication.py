"""Join exact game/input/camera instructions to all stable rendered street lines.

Require separate same-core neutral main and renderer controls, then exact
timeline/PCM equality between those controls. No inferred or fitted frame lag.
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from tools.audit_display_cadence import cameras, measure, rendering_enabled, PHASES
from tools.audit_main_display_latency import bound_report, join
from tools.audit_main_store_latency import parse
from tools.audit_route_loop_cadence import stable_room
from tools.audit_route_store_latency import segments
from tools.audit_uniform_holds import summarize
from tools.benchmark_report import sha, verify_capture
from tools.build_retained_producer_guard import symbols


def equivalent(a, ar, b, br, same_core):
    keys = ('rom_sha256','audio_sha256','scenario_sha256','frames')
    if same_core:
        keys += ('core_sha256',)
    if (not a['capture_complete'] or not b['capture_complete'] or ar != br or
            any(a[k] != b[k] for k in keys) or
            any(r['fault'] or r['input_requested'] != r['input_delivered'] for r in ar)):
        raise ValueError('Incomplete, faulty or non-neutral observer/control')


def store_mismatches(intervals, rows):
    failures = []
    for interval in intervals:
        commit = interval['commit']
        row = rows[commit['frame']-1]
        ram = bytes.fromhex(row['game_ram_hex'])
        if len(ram) != 2048:
            raise ValueError('Incomplete game RAM')
        camera = ram[0xf6]|((ram[0x3d]&1)<<8)
        if camera != commit['camera']:
            failures.append(dict(commit=commit, frame_end_camera=camera, phase=row['phase']))
    return failures


def audit(candidate, main, normal_main, render, normal_render, out):
    if out.exists():
        raise ValueError('Fresh output required')
    observed, rows = verify_capture(main)
    plain, control = verify_capture(normal_main)
    equivalent(observed,rows,plain,control,True)
    rendered, picture_rows = verify_capture(render)
    picture_plain, picture_control = verify_capture(normal_render)
    equivalent(rendered,picture_rows,picture_plain,picture_control,True)
    equivalent(plain,control,picture_plain,picture_control,False)
    renderer_proof = bound_report(render/'renderer-observer.json')
    binding = observed['main_store_observer']
    sources = {**renderer_proof['sources'], **binding['sources']}
    for path,digest in sources.items():
        if sha(Path(path)) != digest:
            raise ValueError('Changed observer source')
    rom = candidate/'native-cpu.sfc'
    if sha(rom) != observed['rom_sha256']:
        raise ValueError('Wrong cartridge')
    labels = symbols(candidate/'native_runtime.lbl')
    points = {0:labels['gameplay_iteration_start'], 1:0xf282,
              2:labels['camera_deferred_nmi_exit']+2, 3:0xf2da}
    trace = Path(binding['trace']['path'])
    if binding['points'] != {str(k):f'{v:04x}' for k,v in points.items()} or sha(trace) != binding['trace']['sha256']:
        raise ValueError('Wrong exact-PC trace')
    with trace.open() as stream:
        loops, outside = parse(csv.reader(stream), points, observed['frames'], rom.read_bytes())
    intervals = [r for r in loops if r['commit'] is not None]
    # Room changes can overwrite F6 later in the same frame. Retain the
    # strict failure, while joining actual instruction values only where the
    # unchanged stable-segment policy supplies complete render coverage.
    overwritten = store_mismatches(intervals, rows)
    wanted = [r['frame'] for i,r in enumerate(rows) if i and
              stable_room(rows[i-1:i+1]) is not None and
              rendering_enabled(rows[i-1],'snes') and rendering_enabled(r,'snes')]
    pixel_binding = rendered['render_scroll_trace']
    pixel_trace = Path(pixel_binding['path'])
    if (sha(pixel_trace) != pixel_binding['sha256'] or pixel_binding['first'] > min(wanted)
            or pixel_binding['last'] < max(wanted)):
        raise ValueError('Incomplete/unbound pixel trace')
    with pixel_trace.open() as stream:
        actual = cameras(csv.DictReader(stream),'snes',wanted)
    phases, excluded = segments(rows,actual)
    joined = join(intervals,phases)
    if {r['commit']['frame'] for r in overwritten} & {r['store_frame'] for r in joined['events']}:
        raise ValueError('Overwritten camera inside a joined stable segment')
    by_commit = {r['commit']['frame']:r for r in intervals}
    if len(by_commit) != len(intervals):
        raise ValueError('Ambiguous multiple commits in a frame')
    for event in joined['events']:
        interval = by_commit[event['store_frame']]
        event['input_frame'] = interval['input']['frame']
        event['input_to_display'] = (None if event['display_frame'] is None else
                                     event['display_frame']-event['input_frame'])
    park = {}
    for name in PHASES:
        selected = [dict(frame=r['frame'],camera=actual[r['frame']][0])
                    for r in rows if r['phase']==name and r['frame'] in actual]
        values = measure(selected)
        park[name] = dict(measured=values, summary=summarize(values))
    rooms = {}
    for room in range(4):
        events = [r for r in joined['events'] if r['phase'].startswith(f'room{room}.')]
        rooms[str(room)] = dict(changes=len(events), **{name:dict(Counter(r[name] for r in events))
                               for name in ('store_to_display','start_to_display','input_to_display')})
    # Existing join tests cover delay/missing-target mutations; this report
    # retains every actual interval and complete series for independent audit.
    paths = [Path(__file__), Path('tools/audit_main_display_latency.py'),
             Path('tools/audit_main_store_latency.py'), Path('tools/audit_route_store_latency.py'),
             Path('tools/audit_display_cadence.py'), Path('tools/audit_uniform_holds.py'),
             Path('tools/audit_route_loop_cadence.py'), Path('tools/build_retained_producer_guard.py'),
             Path('tools/benchmark_report.py'), candidate/'manifest.json',candidate/'native_runtime.lbl',
             rom, trace,pixel_trace,render/'renderer-observer.json']
    paths += [p/n for p in (main,normal_main,render,normal_render) for n in ('capture.json','timeline.json','audio.wav')]
    sources.update({str(p):sha(p) for p in paths})
    report = dict(observer_neutral=True, frames=len(rows), rendered_frames=len(wanted), rooms=rooms,
                  latency=joined, park=park, phases=phases, intervals=intervals, censored=outside,
                  all_frame_end_stores_match=not overwritten, overwritten_stores=overwritten,
                  excluded_rendering_boundaries=excluded, sources=sources, release_ready=False,
                  original_speed_parity_verified=False, physical_input_latency_verified=False,
                  scope=__doc__+' Input means the original input subroutine call, not a physical '
                  'button edge. All frame-end camera inconsistencies remain strict failures; none '
                  'may enter a joined stable segment. Different encounters remain; histograms do '
                  'not prove paired-input equivalence.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(rooms=rooms,missing_display=joined['missing_display'],
        irregular={p:len(r['summary']['short_irregular']) for p,r in park.items()})))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','main','normal-main','render','normal-render','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
