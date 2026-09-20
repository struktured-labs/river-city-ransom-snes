"""Busy-inclusive four-room cadence and original NES sound-wrapper timing.

Independent encounters, not equal-work speed or audible-pop certification.
"""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
import statistics

from tools.audit_busy_combat import classify
from tools.audit_main_display_latency import bound_report
from tools.audit_main_store_latency import parse
from tools.audit_route_loop_cadence import nes_pair
from tools.benchmark_report import sha, verify_capture
from tools.capture_nes_audio_events import POINTS
from tools.nes_event_trace import validate


def context(rows, first, last):
    if not 1 <= first <= last <= len(rows):
        raise ValueError('Timing span outside full timeline')
    # The NES has no port-specific transition state. All original RAM
    # predicates, including actual pause/fade, are identical between systems.
    return classify([dict(r, native=r.get('native') or {'transition_state': 0})
                     for r in rows[first-1:last]])


def cadence(loops, rows):
    rooms = {str(i): [] for i in range(4)}
    excluded = []
    for a, b in zip(loops, loops[1:]):
        first, last = a['start']['frame'], b['start']['frame']
        if (a['start']['clock'] >= a['finish']['clock'] or
                a['finish']['clock'] >= b['start']['clock'] or
                a['finish']['frame'] > last):
            raise ValueError('Overlapping/nonmonotonic complete loops')
        c = context(rows, first, last)
        record = dict(first=first, last=last, frames=last-first,
                      nmi_advances=a['nmi_advances'], context=c,
                      start=a['start'], finish=a['finish'], next_start=b['start'])
        (excluded if c['room'] is None else rooms[str(c['room'])]).append(record)
    summary = {}
    for room, records in rooms.items():
        off = [r for r in records if r['frames'] != 2 or r['nmi_advances'] != 2]
        summary[room] = dict(intervals=len(records), records=records,
            frame_histogram=dict(Counter(str(r['frames']) for r in records)),
            nmi_histogram=dict(Counter(str(r['nmi_advances']) for r in records)),
            busy_intervals=sum(bool(r['context']['busy_frames']) for r in records),
            off_cadence=off, passed=len(records) >= 64 and not off)
    return dict(rooms=summary, excluded=excluded, final_unpaired_loop=loops[-1] if loops else None,
                passed=all(r['passed'] for r in summary.values()), minimum_per_room=64)


def sound_pairs(events):
    active = None
    pairs = []
    censored = []
    for raw in events:
        event = int(raw[3])
        if event not in (3, 4):
            continue
        row = dict(frame=int(raw[0]), line=int(raw[1]), clock=int(raw[2]),
                   task=int(raw[5]), stack=int(raw[12]))
        if event == 3:
            if active is not None:
                raise ValueError('Sound wrapper reentered before return')
            active = row
        elif active is None:
            if pairs or censored:
                raise ValueError('Sound wrapper return without entry')
            censored.append(dict(kind='leading return', event=row))
        else:
            if (row['stack'] != active['stack'] or row['clock'] <= active['clock'] or
                    row['frame'] < active['frame']):
                raise ValueError('Sound wrapper return stack/clock/frame mismatch')
            pairs.append(dict(entry=active, returned=row, cycles=row['clock']-active['clock']))
            active = None
    if active is not None:
        censored.append(dict(kind='trailing entry', event=active))
    if not pairs:
        raise ValueError('No complete sound wrappers')
    return pairs, censored


def spread(values):
    if not values:
        raise ValueError('Empty timing population')
    return dict(count=len(values), minimum=min(values), median=statistics.median(values),
                maximum=max(values), standard_deviation=statistics.pstdev(values))


def sound_timing(pairs, rows):
    selected, excluded = [], []
    for a, b in zip(pairs, pairs[1:]):
        if a['returned']['clock'] >= b['entry']['clock']:
            raise ValueError('Overlapping sound calls')
        c = context(rows, a['entry']['frame'], b['returned']['frame'])
        entry = b['entry']['clock']-a['entry']['clock']
        returned = b['returned']['clock']-a['returned']['clock']
        change = b['cycles']-a['cycles']
        if entry+change != returned:
            raise ValueError('Sound timing decomposition failed')
        r = dict(first=a, second=b, context=c, entry_gap_cycles=entry,
                 return_gap_cycles=returned, duration_change_cycles=change,
                 entry_frame_gap=b['entry']['frame']-a['entry']['frame'])
        (selected if c['room'] is not None else excluded).append(r)
    return dict(intervals=selected, excluded=excluded,
        entry_gap_cycles=spread([r['entry_gap_cycles'] for r in selected]),
        return_gap_cycles=spread([r['return_gap_cycles'] for r in selected]),
        entry_frame_histogram=dict(Counter(str(r['entry_frame_gap']) for r in selected)),
        non_one_frame=[r for r in selected if r['entry_frame_gap'] != 1],
        scope='NES CPU cycles, not SNES master clocks or SPC ticks; exact wrapper PCs. '
              'Driver return is not an audio DAC timestamp. No fitted cross-system clock offset.')


def neutral(observed, normal):
    a, rows = verify_capture(observed)
    b, baseline = verify_capture(normal)
    if (not a['capture_complete'] or not b['capture_complete'] or rows != baseline or
            any(a[k] != b[k] for k in ('system', 'core_sha256', 'rom_sha256',
                                     'scenario_sha256', 'frames', 'audio_sha256'))):
        raise ValueError('Observer lacks exact same-core full timeline/PCM control')
    return a, rows


def audit(candidate, snes, normal_snes, nes, normal_nes, school, out):
    if out.exists():
        raise ValueError('Fresh review required')
    sr, srows = neutral(snes, normal_snes)
    nr, nrows = neutral(nes, normal_nes)
    nb = bound_report(nes/'nes-audio-events.json')
    sb = sr['main_store_observer']
    rom = candidate/'native-cpu.sfc'
    if (not nb['observer_neutral'] or sr['rom_sha256'] != sha(rom) or
            sr['scenario_sha256'] != nr['scenario_sha256'] or nb['points'] != POINTS):
        raise ValueError('Different ROM, route or trace points')
    sources = {**nb['sources'], **sb['sources']}
    st = Path(sb['trace']['path'])
    nt = Path(nb['trace'])
    if sha(st) != sb['trace']['sha256'] or sha(nt) != sources.get(str(nt)):
        raise ValueError('Unbound traces')
    labels = candidate/'native_runtime.lbl'
    syms = {s.split()[2].lstrip('.'): int(s.split()[1], 16)
            for s in labels.read_text().splitlines()}
    points = {0: syms['gameplay_iteration_start'], 1: 0xf282,
              2: syms['camera_deferred_nmi_exit']+2, 3: 0xf2da}
    if sb['points'] != {str(k): f'{v:04x}' for k, v in points.items()}:
        raise ValueError('Incorrect SNES trace points')
    with st.open() as f:
        sl, sc = parse(csv.reader(f), points, sr['frames'], rom.read_bytes())
    for loop in sl:
        loop['nmi_advances'] = (loop['finish']['nmi']-loop['start']['nmi']) & 65535
    with nt.open() as f:
        events = list(csv.reader(f))
    validate(events, 1, nr['frames'], nr['frames'], POINTS)
    nl, nc = nes_pair([r for r in events if int(r[3]) < 3])
    pairs, pc = sound_pairs(events)
    fades = bound_report(school/'report.json')
    if (not fades['passed'] or fades['sources'].get(str(rom)) != sha(rom)):
        raise ValueError('School-return evidence failing or different ROM')
    sources.update(fades['sources'])
    for root, receipt in ((snes, sr), (normal_snes, sr), (nes, nr), (normal_nes, nr)):
        for name in ('capture.json', 'timeline.json', 'audio.wav'):
            p = root/name
            sources[str(p)] = sha(p)
    for name in (__file__, 'tools/audit_busy_combat.py', 'tools/audit_main_store_latency.py',
                 'tools/audit_route_loop_cadence.py', 'tools/audit_main_display_latency.py',
                 'tools/benchmark_report.py', 'tools/nes_event_trace.py',
                 'tests/test_ordinary_route_timing.py'):
        p = Path(name); sources[str(p)] = sha(p)
    for p in (rom, labels, st, nt, nes/'nes-audio-events.json', school/'report.json'):
        sources[str(p)] = sha(p)
    for p, digest in sources.items():
        if sha(Path(p)) != digest:
            raise ValueError('Source changed: '+p)
    result = dict(rom_sha256=sha(rom), observer_neutral=True,
        snes=cadence(sl, srows), nes=cadence(nl, nrows),
        censored=dict(snes=sc, nes=nc, nes_sound=pc), nes_sound=sound_timing(pairs, nrows),
        school_return={k: fades[k] for k in ('passed', 'gates', 'samples')},
        sources=sources, release_ready=False, physical_verified=False,
        matched_encounter_speed_verified=False, pop_free_verified=False,
        scope=__doc__+' All consecutive loop pairs are considered before exclusions. '
        'Original NMI-busy flag is retained. Task/pause/fade/transition/room exclusions '
        'and all off-cadence loops are preserved. NES and SNES execute independent '
        'encounters and different route lengths; no cross-platform FPS ratio.')
    out.mkdir(parents=True)
    table = '<table><tr><th>System / room</th><th>Intervals</th><th>Frame gaps</th><th>NMI advances</th><th>Busy included</th></tr>'
    for system in ('nes', 'snes'):
        for room, r in result[system]['rooms'].items():
            table += '<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in
                (f'{system.upper()} / {room}', r['intervals'], r['frame_histogram'],
                 r['nmi_histogram'], r['busy_intervals']))+'</tr>'
    page = '<!doctype html><meta charset="utf-8"><title>Current four-room timing</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}a{color:cyan}td,th{padding:10px;border:1px solid #456}table{border-collapse:collapse}pre{white-space:pre-wrap}</style>'
    page += '<h1>Current four-room timing</h1><p>'+html.escape(result['scope'])+'</p>'+table+'</table>'
    page += '<h2>Original NES sound wrapper</h2><pre>'+html.escape(json.dumps({k:result['nes_sound'][k] for k in ('entry_gap_cycles', 'return_gap_cycles', 'entry_frame_histogram')}, indent=2))+'</pre><p>'+html.escape(result['nes_sound']['scope'])+'</p>'
    page += '<h2>School return: PASS</h2><p>All 40 fixed background offsets match. First nonblack offset: 7 on both systems.</p><p><a href="../'+school.name+'/">NES/SNES fade collage</a> · <a href="report.json">Complete raw measurements, exclusions and hashes</a></p>'
    (out/'index.html').write_text(page)
    result['artifacts'] = {'index.html': sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({s:{k:{n:v[n] for n in ('intervals','frame_histogram','nmi_histogram','busy_intervals','passed')} for k,v in result[s]['rooms'].items()} for s in ('nes','snes')}, indent=2))
    print(json.dumps({k:result['nes_sound'][k] for k in ('entry_gap_cycles','return_gap_cycles','entry_frame_histogram')}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','snes','normal-snes','nes','normal-nes','school','out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
