"""Explain each long renderer hold using exact camera stores; never waive speed gates."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
import shutil

from tools.audit_display_cadence import measure, observe
from tools.audit_main_display_latency import bound_report, join
from tools.audit_main_store_latency import parse
from tools.audit_nes_main_phase import pair
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.nes_event_trace import validate
from tools.review_candidate_combat import native_clip


def classify(phases, iterations, rows, system):
    if system not in ('nes', 'snes'):
        raise ValueError('Unknown system')
    commits = [r for r in iterations if r.get('commit') is not None]
    if any(b['commit']['frame'] <= a['commit']['frame'] for a, b in zip(commits, commits[1:])):
        raise ValueError('Unordered camera commits')
    if len(rows) < 2 or any(r['frame'] != i+1 for i, r in enumerate(rows)):
        raise ValueError('Need complete consecutive timeline')
    result = []
    for phase, data in phases.items():
        if json.loads(json.dumps(measure(data['series']))) != json.loads(json.dumps(data)):
            raise ValueError('Camera intervals differ from rendered series')
        display = {r['frame']: r['camera'] for r in data['series']}
        for hold in data['intervals']:
            if hold['frames'] <= 4:
                continue
            first, last = hold['start'], hold['end']
            work = [r for r in commits if first-1 <= r['commit']['frame'] <= last-1]
            covered = bool(work and work[0]['commit']['frame'] == first-1
                           and work[-1]['commit']['frame'] == last-1)
            regular = covered and len(work) > 1 and all(
                b['start']['frame']-a['start']['frame'] == 2
                and b['commit']['frame']-a['commit']['frame'] == 2
                for a, b in zip(work, work[1:]))
            # Full SNES start/input/store/finish chain is available. NES trace
            # observes only start/input/store, so do not imply finish timing.
            complete = None if system == 'nes' else bool(work) and all(
                r.get('nmi_advances') == 2 and r['finish']['frame']-r['start']['frame'] == 2
                for r in work)
            visible = covered and all(display.get(f) == r['commit']['camera']
                for i, r in enumerate(work)
                for f in range(r['commit']['frame']+1,
                    work[i+1]['commit']['frame']+1 if i+1 < len(work) else last+1))
            repeats = sum(a['commit']['camera'] == b['commit']['camera']
                          for a, b in zip(work, work[1:]))
            supported = bool(covered and regular and visible and repeats and complete is not False)
            context = []
            for row in rows[max(0, first-31):min(len(rows), last+3)]:
                ram = bytes.fromhex(row['game_ram_hex'])
                if len(ram) != 2048:
                    raise ValueError('Missing full original game RAM')
                context.append(dict(frame=row['frame'], phase=row['phase'],
                    player_x=ram[0x388]+256*ram[0x390], player_y=ram[0x398],
                    working_camera=ram[0xDC]+256*ram[0xDD],
                    committed_camera=ram[0xF6]+256*(ram[0x3D]&1),
                    raw_0300_0307=ram[0x300:0x308].hex(),
                    completion_counter_052b=ram[0x52B],
                    input_requested=row['input_requested'], input_delivered=row['input_delivered']))
            result.append(dict(phase=phase, hold=hold, iterations=work, context=context,
                endpoint_stores_covered=covered, two_frame_start_and_store_cadence=regular,
                complete_snes_two_tick_loops=complete, every_store_visible_next_frame=visible,
                repeated_camera_commits=repeats,
                classification='repeated_command_regular_updates' if supported else 'unresolved'))
    return result


def audit(out):
    if out.exists():
        raise ValueError('Fresh report required')
    candidate = Path('build/compact-pair-trial-2242')
    normal = dict(nes=Path('build/park-hold-nes-normal-2271'),
                  snes=Path('build/compact-pair-main-normal-2259'))
    observed = dict(nes=Path('build/park-hold-nes-observed-2272'),
                    snes=Path('build/compact-pair-main-2260'))
    renderer = dict(nes=observed['nes'], snes=Path('build/compact-pair-render-2256'))
    render_control = dict(nes=normal['nes'], snes=Path('build/compact-pair-route-2246'))
    results, sources, frames = {}, {}, {}
    for system in ('nes', 'snes'):
        receipt, rows = verify_capture(observed[system])
        control, plain = verify_capture(normal[system])
        equivalent(receipt, rows, control, plain)
        rr, rrows = verify_capture(renderer[system])
        rc, rplain = verify_capture(render_control[system])
        equivalent(rr, rrows, rc, rplain)
        if rows != rrows or receipt['audio_sha256'] != rr['audio_sha256']:
            raise ValueError('Main and renderer episodes differ')
        rendered = observe(renderer[system], render_control[system], system)
        if system == 'nes':
            binding = receipt['nes_event_trace']
            trace = Path(binding['path'])
            points = {'0': 'f27d', '1': 'e2b1', '2': 'f282'}
            if sha(trace) != binding['sha256'] or binding['points'] != points:
                raise ValueError('Wrong NES event binding')
            rom = Path('roms/river-city-ransom-us.nes')
            if sha(rom) != receipt['rom_sha256']:
                raise ValueError('Changed original NES ROM')
            image = rom.read_bytes()
            for pc, wanted in ((0xF27D, bytes.fromhex('a9008d0b01')),
                               (0xE2B1, bytes.fromhex('85f6')),
                               (0xF282, bytes.fromhex('2031f7'))):
                at = 16+0x10000+pc
                if image[at:at+len(wanted)] != wanted:
                    raise ValueError('Changed original NES instruction')
            with trace.open() as stream:
                events = list(csv.reader(stream))
            validate(events, binding['first'], binding['last'], receipt['frames'], points)
            loops, censored = pair(events)
        else:
            binding = receipt['main_store_observer']
            for name, digest in binding['sources'].items():
                if sha(Path(name)) != digest:
                    raise ValueError('Changed main observer source')
                sources[name] = digest
            trace = Path(binding['trace']['path'])
            if sha(trace) != binding['trace']['sha256']:
                raise ValueError('Changed main trace')
            symbols = {s.split()[2].lstrip('.'): int(s.split()[1], 16)
                       for s in (candidate/'native_runtime.lbl').read_text().splitlines()}
            points = {0: symbols['gameplay_iteration_start'], 1: 0xF282,
                      2: symbols['camera_deferred_nmi_exit']+2, 3: 0xF2DA}
            if binding['points'] != {str(k): f'{v:04x}' for k, v in points.items()}:
                raise ValueError('Different linked main trace')
            rom = candidate/'native-cpu.sfc'
            if sha(rom) != receipt['rom_sha256']:
                raise ValueError('Changed candidate cartridge')
            with trace.open() as stream:
                loops, censored = parse(csv.reader(stream), points, receipt['frames'], rom.read_bytes())
            for loop in loops:
                loop['nmi_advances'] = (loop['finish']['nmi']-loop['start']['nmi']) & 65535
        intervals = [r for r in loops if r.get('commit') is not None]
        holds = classify(rendered['phases'], intervals, rows, system)
        results[system] = dict(holds=holds, rendered=rendered, censored=censored,
            changed_store_publication=join(intervals, rendered['phases']),
            summary=dict(long_holds=len(holds), classifications=dict(Counter(e['classification'] for e in holds)),
                         durations=dict(Counter(e['hold']['frames'] for e in holds))))
        frames[system] = rows
        sources.update(rendered['sources'])
        for root in set((normal[system], observed[system], renderer[system], render_control[system])):
            for name in ('capture.json', 'timeline.json', 'audio.wav'):
                sources[str(root/name)] = sha(root/name)
        sources[str(trace)] = sha(trace)
        sources[str(rom)] = sha(rom)
    # This explanation must reject delayed publication and dropped updates.
    sample = results['snes']
    first = sample['holds'][0]
    bad_phases = json.loads(json.dumps(sample['rendered']['phases']))
    phase = bad_phases[first['phase']]
    endpoint = first['hold']['end']
    series = phase['series']
    at = next(i for i, r in enumerate(series) if r['frame'] == endpoint)
    series[at]['camera'] = series[at-1]['camera']
    bad_phases[first['phase']] = measure(series)
    snes_loops = intervals
    delayed = classify(bad_phases, snes_loops, frames['snes'], 'snes')
    dropped = json.loads(json.dumps(snes_loops))
    dropped.remove(next(r for r in dropped if r['commit']['frame'] == first['hold']['start']+1))
    missing = classify(sample['rendered']['phases'], dropped, frames['snes'], 'snes')
    if first['classification'] != 'repeated_command_regular_updates':
        raise ValueError('Need an explained baseline for sensitivity tests')
    def rejected_target(events):
        selected = [e for e in events if e['phase'] == first['phase']
                    and e['hold']['start'] == first['hold']['start']]
        return len(selected) == 1 and selected[0]['classification'] == 'unresolved'
    mutants = dict(delayed_display=rejected_target(delayed), dropped_update=rejected_target(missing))
    if not all(mutants.values()):
        raise ValueError('Hold explanation accepted corrupted observation')
    out.mkdir(parents=True)
    cards = []
    for system, result in results.items():
        cards.append('<h2>'+system.upper()+'</h2><pre>'+html.escape(json.dumps(result['summary'], indent=2))+'</pre>')
        for i, event in enumerate(result['holds']):
            first, last = event['hold']['start'], event['hold']['end']
            prefix = f'{system}-{first}'
            cards.append(f'<h3>{prefix}: {last-first} frames — {event["classification"]}</h3><div class="grid">')
            event['pictures'] = []
            for frame in sorted({first, first+2, (first+last)//2, last-2, last}):
                row = frames[system][frame-1]
                source = normal[system]/row['frame_image']
                if sha(source) != row['frame_image_sha256']:
                    raise ValueError('Changed hold screenshot')
                name = f'{prefix}-{frame}.png'
                shutil.copyfile(source, out/name)
                sources[str(source)] = sha(source)
                event['pictures'].append(dict(frame=frame, file=name, sha256=sha(out/name)))
                cards.append(f'<figure><img src="{name}"><figcaption>Frame {frame}</figcaption></figure>')
            start_row, end_row = frames[system][max(0, first-31)], frames[system][min(len(frames[system])-1, last+29)]
            event['audio'] = native_clip(normal[system]/'audio.wav', out/(prefix+'.wav'),
                start_row['audio_start_sample'], end_row['audio_start_sample']+end_row['audio']['samples'])
            cards.append(f'</div><audio controls preload="none" src="{prefix}.wav"></audio>')
    for name in (__file__, 'tools/audit_display_cadence.py', 'tools/audit_main_display_latency.py',
            'tools/audit_main_store_latency.py', 'tools/audit_nes_main_phase.py', 'tools/nes_event_trace.py',
            'tools/benchmark_report.py', 'tools/capture_combat_instructions.py', 'tools/review_candidate_combat.py',
            'tests/test_current_park_holds.py'):
        sources[str(name)] = sha(Path(name))
    nes_core = Path('.deps/fceumm-raster/rcr_raster_libretro.so')
    if sha(nes_core) != verify_capture(normal['nes'])[0]['core_sha256']:
        raise ValueError('Different original observer core')
    sources[str(nes_core)] = sha(nes_core)
    if any(sha(Path(name)) != digest for name, digest in sources.items()):
        raise ValueError('Source changed during audit')
    report = dict(systems=results, derived_mutants_rejected=mutants, sources=sources,
        release_ready=False, physical_holds_explained=False, matched_encounters=False,
        scope='All renderer holds longer than four frames in both park sweep phases. Exact original '
        'camera stores and every covered displayed frame test an explicit next-frame publication hypothesis. '
        'Repeated commands with regular updates distinguish these measured holds from missed renderer '
        'updates, but do not establish game-motion cause. NES start/input/store observations do not '
        'measure completion; SNES complete two-tick chains additionally checked. Independent encounters '
        'are not per-event NES/SNES matches. All unresolved/long intervals, native audio and pictures '
        'retained; no physical hold, popping, loading or full-game speed waiver.')
    page = '<!doctype html><meta charset="utf-8"><title>Long park holds: command or renderer?</title><style>body{font:17px system-ui;background:#101820;color:#eef;max-width:1250px;margin:30px auto}a{color:#8df}.grid{display:flex;flex-wrap:wrap}img{width:224px;image-rendering:pixelated}figure{margin:8px}pre{white-space:pre-wrap}audio{width:100%}</style>'
    page += '<h1>Long park holds: exact camera commands versus display</h1><p>'+html.escape(report['scope'])+'</p><p><a href="report.json">Every store, frame, input and source binding</a> · <a href="manifest.json">Artifact hashes</a></p>'+''.join(cards)
    (out/'index.html').write_text(page)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'manifest.json').write_text(json.dumps(dict(sources=sources,
        artifacts={p.name: sha(p) for p in out.iterdir() if p.is_file()}), indent=2)+'\n')
    print(json.dumps({system: r['summary'] for system, r in results.items()}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    audit(**vars(p.parse_args()))
