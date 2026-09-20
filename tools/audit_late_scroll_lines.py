"""Inspect fixed late-publication frames with a neutral actual-renderer trace."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.audit_render_scroll import bands, load_lines
from tools.audit_background_sweep import neutral
from tools.audit_scroll_publication import frame_path
from tools.benchmark_report import sha, verify_capture


def audit(sweep, background, normal, renderer, out):
    failed = json.loads((sweep/'report.json').read_text())
    if not failed['late_publications']:
        raise ValueError('Need original late-publication samples')
    if failed['sources']['snes']['capture_sha256'] != sha(background/'capture.json'):
        raise ValueError('Sweep uses a different capture')
    baseline, rows = verify_capture(normal)
    for root in (background, renderer):
        observed, timeline = verify_capture(root)
        # Only the separately bound background plane is extra timeline data.
        same_timeline = neutral((observed,timeline),(baseline,rows)) if root == background else timeline == rows
        if (not observed['capture_complete'] or not same_timeline or
                any(observed[k] != baseline[k] for k in
                    ('rom_sha256', 'scenario_sha256', 'audio_sha256', 'frames'))):
            raise ValueError('Observer changed execution')
    trace = renderer.with_suffix('.csv')
    receipt, _ = verify_capture(renderer)
    if receipt['render_scroll_trace']['sha256'] != sha(trace):
        raise ValueError('Unbound renderer trace')
    frames = sorted({f+delta for r in failed['late_publications']
                     for f in (r['frame'],) for delta in (-1,0,1)})
    rendered = load_lines(trace, 'snes', frames)
    by_frame = {r['frame']:r for r in rows}
    out.mkdir(parents=True, exist_ok=False)
    samples, cards = [], []
    artifacts = []
    for frame in frames:
        row = by_frame[frame]
        ram = bytes.fromhex(row['game_ram_hex'])
        committed = ram[0xf6] | ((ram[0x3d] & 1) << 8)
        sample = dict(frame=frame, room=ram[0x42],
            working=int.from_bytes(ram[0xdc:0xde], 'little'), committed=committed,
            frame_end_published=row['native']['hdma_street_scroll_x'],
            renderer_bands=bands(rendered[frame]),
            all_lines_match_frame_end_committed=set(rendered[frame].values()) == {committed})
        samples.append(sample)
        source = frame_path(background, row)
        target = out/f'{frame}.png'
        shutil.copyfile(source, target)
        artifacts += [source, target]
        cards.append(f'<figure><img src="{frame}.png"><figcaption>'+
                     html.escape(json.dumps(sample))+'</figcaption></figure>')
    sources = [Path(__file__), Path('tools/audit_render_scroll.py'),
               Path('tools/audit_background_sweep.py'), sweep/'report.json', trace,
               *[r/'capture.json' for r in (background,normal,renderer)], *artifacts]
    report = dict(observer_neutral=True, release_ready=False,
        original_sweep_passed=failed['passed'], original_late_publications=failed['late_publications'],
        samples=samples, sources={str(p):sha(p) for p in sources},
        scope='Original flagged frames and adjacent frames, all 160 renderer lines; no '
              'rematching, shifted images or relaxed sweep gates. End-of-frame committed '
              'state is not assumed to have existed before the render deadline. '
              'A mismatch requires CPU/deadline diagnosis; not a whole-game scrolling verdict.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Late scroll lines</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;margin:30px}a{color:#9df}'
        'section{display:flex;gap:15px;flex-wrap:wrap}figure{width:384px;margin:0}'
        'img{width:100%;image-rendering:pixelated}figcaption{overflow-wrap:anywhere}</style>'
        '<h1>Actual renderer at the original late-publication frame</h1><p>'+html.escape(report['scope'])+
        '</p><p><a href="report.json">Bound measurements</a></p><section>'+''.join(cards)+'</section>')
    print(json.dumps(samples, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('sweep','background','normal','renderer','out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
