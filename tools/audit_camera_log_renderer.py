"""Compare actual scanline observations while retaining non-camera observer failures."""
import argparse
import csv
import html
from itertools import zip_longest
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def compare_lines(left, right):
    mismatches = []
    counts = [0, 0]
    for index, (a, b) in enumerate(zip_longest(left, right), 1):
        counts[0] += a is not None
        counts[1] += b is not None
        if a != b:
            mismatches.append(dict(row=index, baseline=a, diagnostic=b))
    return dict(baseline_rows=counts[0], diagnostic_rows=counts[1],
                exact=bool(counts[0]) and not mismatches, mismatches=mismatches)


def audit(parent, diagnostic, review, out):
    if out.exists():
        raise ValueError('Fresh output required')
    evidence = bound_report(review/'report.json')
    runs = evidence['results']['wait-route']
    if not runs['complete'] or not runs['camera_fields_exact'] or runs['neutral']:
        raise ValueError('Need complete, camera-matching but non-neutral logger qualification')
    sources = dict(evidence['sources'])
    traces = []
    receipts = []
    for folder in (parent, diagnostic):
        p = folder/'renderer-observer.json'
        proof = bound_report(p)
        if not proof['observer_neutral']:
            raise ValueError('Unqualified host renderer observer')
        sources.update(proof['sources'])
        sources[str(p)] = sha(p)
        traces.append(Path(proof['trace']))
        receipts.append(json.loads((folder/'capture.json').read_text()))
    for key in ('core_sha256', 'scenario_sha256', 'frames', 'capture_complete'):
        if receipts[0][key] != receipts[1][key]:
            raise ValueError('Mismatched renderer replay: '+key)
    # Bind these renderer ROMs to the ordinary captures used in review2444.
    for label, receipt in zip(('baseline', 'trial'), receipts):
        name = 'build/camera-route-control-2439/capture.json' if label == 'baseline' else 'build/camera-wait-route-2441/capture.json'
        if name not in evidence['sources'] or json.loads(Path(name).read_text())['rom_sha256'] != receipt['rom_sha256']:
            raise ValueError('Renderer cartridge is not the reviewed replay')
    with traces[0].open() as a, traces[1].open() as b:
        left, right = csv.DictReader(a), csv.DictReader(b)
        required = ['frame', 'line', 'h_offset', 'v_offset', 'mode', 'main_screen', 'forced_blank']
        if left.fieldnames != required or right.fieldnames != required:
            raise ValueError('Wrong renderer schema')
        result = compare_lines(left, right)
    for p in (Path(__file__), Path('tests/test_camera_log_renderer.py'), review/'report.json'):
        sources[str(p)] = sha(p)
    report = dict(camera_scanline_match=result, frames=receipts[0]['frames'],
                  camera_only_passed=result['exact'], full_observer_neutral=False,
                  physical_deployed=False, physical_speed_verified=False, pop_free_verified=False,
                  release_ready=False, sources=sources,
                  scope='All recorded renderer rows compared in order, including vertical offset, '
                  'mode, main-screen and blanking state; no selected camera window or alignment. '
                  'Both host renderer runs reproduce their own ordinary-core full timeline and PCM. '
                  'This is a scoped camera match for this route only. Cartridge recording still '
                  'changes sprite frames and native audio, and cannot certify those subsystems. '
                  'No physical capture or worst-case interrupt-latency proof.')
    out.mkdir(parents=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Camera logger scanlines</title>'
        '<style>body{background:#101820;color:#eef;font:18px system-ui;max-width:1000px;margin:40px auto}a{color:#8df}</style>'
        '<h1>Camera-only renderer comparison</h1><p>'+html.escape(report['scope'])+'</p>'
        f'<p>{report["frames"]:,} frames; {result["baseline_rows"]:,} baseline renderer rows; '
        f'{result["diagnostic_rows"]:,} diagnostic rows; {len(result["mismatches"]):,} differences.</p>'
        '<p>Full recorder neutrality: FAIL. Hardware deployment: NO.</p>'
        '<p><a href="../camera-wait-review-2444/">Sprite differences and native audio</a> · '
        '<a href="report.json">Source-bound report</a></p>')
    report['artifacts'] = {'index.html': sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(camera_only_passed=report['camera_only_passed'],
                         rows=result['baseline_rows'], differences=len(result['mismatches']))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'diagnostic', 'review', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
