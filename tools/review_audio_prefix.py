"""Authenticate the shorter replay against the full-route audio fault."""
import argparse
import csv
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.audit_sound_service_phases import pair
from tools.benchmark_report import sha


def review(normal, observed, full, out):
    if out.exists():
        raise ValueError('Fresh output required')
    a = bound_report(normal / 'audio-prefix.json')
    b = bound_report(observed / 'audio-prefix.json')
    c = bound_report(full / 'sound-service.json')
    if (not a['full_prefix_equal'] or not b['observer_neutral'] or not c['observer_neutral']
            or b['control'] != str(normal) or a['frames'] != b['frames']):
        raise ValueError('Missing authenticated prefix/control chain')
    source_control = str(Path(a['full']) / 'capture.json')
    if c['sources'].get(source_control) != a['sources'].get(source_control):
        raise ValueError('Full observer belongs to a different primary control')
    if not b.get('post_exit_finalization'):
        raise ValueError('Trace hashes must be finalized after producer exit')
    def read(path):
        with Path(path).open() as stream:
            return list(csv.reader(stream))
    short = read(b['traces']['RCR_MAIN_STORE_TRACE'])
    entire = read(c['trace'])
    expected = [r for r in entire if int(r[1]) <= b['frames']]
    if short != expected:
        raise ValueError('Short observer lost or changed service events')
    calls, gaps = pair(short)
    target = [r for r in gaps if r['current']['entry']['frame'] == 2120]
    if len(target) != 1 or target[0]['return_gap_ms'] < 23:
        raise ValueError('Known late-service symptom missing')
    sources = {**a['sources'], **b['sources'], **c['sources']}
    for p in (Path(__file__), Path('tools/audit_sound_service_phases.py'),
              Path('tests/test_audio_prefix.py'), normal / 'audio-prefix.json',
              observed / 'audio-prefix.json', full / 'sound-service.json'):
        sources[str(p)] = sha(p)
    report = dict(sources=sources, prefix_frames=b['frames'], full_frames=c['frames'],
        exact_service_events=True, complete_calls=len(calls), target=target[0],
        timing=dict(normal=a['timing'], observed=b['timing'], post_exit=b['post_exit_finalization'],
                    historical_full_observed_replay_seconds=c['replay_seconds']),
        all_service_intervals=gaps, release_ready=False,
        scope=__doc__ + ' Full replay timing is historical, not simultaneous controlled '
        'benchmarking. Prefix/full outputs agree exactly in the covered interval; '
        'remaining route and full-game acceptance still require separate tests.')
    out.mkdir(parents=True)
    (out / 'index.html').write_text('<!doctype html><meta charset="utf-8">'
        '<title>Short audio test loop</title><style>body{background:#091016;color:#e8f2f7;'
        'font:18px/1.6 system-ui;max-width:900px;margin:40px auto;padding:20px}a{color:#6de5e8}</style>'
        '<h1>Shorter audio loop, same reproduced fault</h1>'
        f'<p>{b["frames"]:,} boot-driven frames instead of {c["frames"]:,}. '
        'No save-state edits, retiming, sample normalization or input changes.</p>'
        f'<p>Fresh observed replay: <strong>{b["timing"]["replay_seconds"]:.2f}s</strong>; '
        f'with control verification: <strong>{b["timing"]["total_seconds"]:.2f}s</strong>. '
        f'Historical full observed replay: {c["replay_seconds"]:.2f}s (replay only).</p>'
        '<p>Every primary frame/state/input field and native PCM sample matches the full '
        'run over this prefix. Image-derived waypoint telemetry is recomputed from the '
        'actual captured images. A separate same-core observer/control pair also matches.</p>'
        f'<p>All {len(short):,} service events exactly match the full trace. '
        f'The known late return gap remains <strong>{target[0]["return_gap_ms"]:.3f}ms</strong>; '
        'the faster loop did not remove the failing interval.</p>'
        '<p>The first verification attempt rejected a tuple/list serialization mismatch '
        'and is retained as3729. Five focused unit tests pass, including changed-frame '
        'and changed-cursor rejection.</p>'
        '<p>This is test-cycle improvement, not a cartridge fix or full-route qualification.</p>'
        '<p><a href="report.json">Bound timings and every service interval</a> · '
        '<a href="../progress-3728/">Project progress</a> · '
        '<a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/14">Test loop issue #14</a></p>')
    report['artifacts'] = {'index.html': sha(out / 'index.html')}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(frames=b['frames'], events=len(short), timing=report['timing'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('normal', 'observed', 'full', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    review(**vars(parser.parse_args()))
