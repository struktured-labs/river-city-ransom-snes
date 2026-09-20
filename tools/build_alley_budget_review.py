"""Publish unchanged room-entry screenshots and rejected budget trials."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha


def validate_entry(report, root):
    if report['audit_sha256'] != sha(Path('tools/audit_room_entry.py')):
        raise ValueError('Different room-entry auditor')
    if [r['room'] for r in report['comparisons']] != [1, 2, 3]:
        raise ValueError('Missing or reordered room coverage')
    capture = json.loads((root/'capture.json').read_text())
    binding = report['sources']['snes']
    if (binding['capture_sha256'] != sha(root/'capture.json') or
            binding['rom_sha256'] != capture['rom_sha256'] or not capture['capture_complete']):
        raise ValueError('Different or incomplete candidate capture')
    if any(len(r['mismatch_pixels_by_offset']) != 40 for r in report['comparisons']):
        raise ValueError('Incomplete fade comparison')


def build(out):
    cases = [('Current: 16 rows', 'postpublish-entry-1371', 'postpublish-normal-1322'),
             ('Trial: 8 rows', 'hidden-budget8-entry-1382', 'hidden-budget8-normal-1379'),
             ('Trial: 12 rows', 'hidden-budget12-entry-1383', 'hidden-budget12-normal-1380')]
    reports = []
    sources = {str(Path(__file__)): sha(Path(__file__))}
    for label, audit, capture in cases:
        path = Path('build')/audit/'report.json'
        report = json.loads(path.read_text())
        validate_entry(report, Path('build')/capture)
        sources[str(path)] = sha(path)
        sources[str(Path('build')/capture/'capture.json')] = sha(Path('build')/capture/'capture.json')
        reports.append(report)
    if any(r['sources']['nes'] != reports[0]['sources']['nes'] for r in reports):
        raise ValueError('Different NES reference')
    work_path = Path('build/alley-main-phases-1384/report.json')
    work = json.loads(work_path.read_text())
    if (not work['observer_neutral'] or
            work['rom_sha256'] != reports[0]['sources']['snes']['rom_sha256']):
        raise ValueError('Wrong or nonneutral instruction profile')
    for path, digest in work['sources'].items():
        if sha(Path(path)) != digest:
            raise ValueError('Changed profile source: '+path)
    out.mkdir(parents=True, exist_ok=False)

    def copy(path, name):
        shutil.copyfile(path, out/name)
        sources[str(path)] = sha(path)

    copy(work_path, 'work.json')
    table = []
    collages = []
    for room in range(1,4):
        reference = reports[0]['comparisons'][room-1]['nes']
        for label, report in [('NES', None), *zip((c[0] for c in cases), reports)]:
            c = None if report is None else report['comparisons'][room-1]
            r = reference if c is None else c['snes']
            offsets = 'reference' if c is None else ', '.join(str(i) for i,n in
                enumerate(c['mismatch_pixels_by_offset']) if n) or 'none'
            table.append(f'<tr><td>{room}</td><td>{label}</td><td>{r["room_change_to_visible"]}</td>'
                f'<td>{r["rendering_off_to_visible"]}</td><td>{r["first_nonblack_offset"]}</td><td>{offsets}</td></tr>')
        cards = []
        images = [('NES', cases[0][1], 'nes'), *[(c[0], c[1], 'snes') for c in cases]]
        for i,(label,directory,side) in enumerate(images):
            name = f'room-{room}-offset7-{i}.png'
            copy(Path('build')/directory/f'room-{room}-07-{side}.png', name)
            cards.append(f'<figure><img src="{name}" alt="Room {room}, {label}, rendering-enable plus seven">'
                         f'<figcaption>{label}</figcaption></figure>')
        collages.append(f'<h3>Room {room}: rendering-enable +7 frames</h3><section>'+''.join(cards)+'</section>')
    costs = []
    for interrupt in work['interrupts']:
        stage = next(s for s in interrupt['stages'] if s['name']=='native_prepare')
        phases = stage['phases']
        if sum(p['elapsed_clocks'] for p in phases) != stage['elapsed_clocks']:
            raise ValueError('Producer phase costs do not partition the call')
        costs.append('<tr><td>'+str(interrupt['entry']['frame'])+'</td><td>'+str(interrupt['elapsed_clocks'])+
            '</td><td>'+str(stage['hidden_direct_row_calls'])+'</td>'+''.join(
                '<td>'+str(p['elapsed_clocks'])+'</td>' for p in phases)+'</tr>')
    links = []
    for i,(label,directory,_) in enumerate(cases):
        copy(Path('build')/directory/'report.json', f'entry-{i}.json')
        links.append(f'<a href="../{directory}/">{label}: complete audit</a>')
    page = '''<!doctype html><meta charset="utf-8"><title>Alley loading: measured regression</title>
<style>body{background:#101821;color:#eaf0f7;font:16px/1.5 system-ui;max-width:1400px;margin:24px auto;padding:16px}
a{color:#9df}table{border-collapse:collapse}td,th{border:1px solid #567;padding:7px}
section{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}figure{margin:0}
img{width:100%;image-rendering:pixelated}.open{border-left:4px solid #eaa747;padding-left:14px}</style>
<h1>Alley loading: a real timing regression, not a new release</h1>
<p>Current cartridge fa882cb61138. No Rival restart, controller change or game graphics change.</p>
<p class="open">Both trials fail overall acceptance. Eight rows fixes the alley fade but regresses mall/park.
Twelve rows improves later alley colors but still misses first visibility. Neither is promoted.</p>
<h2>Frames until scenery appears</h2>
<p>Anchors come from game/PPU state. All forty fixed-offset backgrounds are compared, without phase shifting.
Different encounter histories mean total route duration is not an equal-work speed benchmark.</p>
<table><tr><th>Room</th><th>Build</th><th>From room change</th><th>From rendering off</th>
<th>From rendering on</th><th>Differing fade offsets</th></tr>'''+''.join(table)+'''</table>
<h2>Unchanged frame captures</h2><p>One fixed offset across all three rooms and all builds; not a best-match selection.
These are original composed screenshots. Numeric comparisons use the fixed background band, excluding actors.</p>'''+''.join(collages)+'''
<h2>Where the current alley interrupt spends time</h2>
<p>Master-clock elapsed measurements include DMA/events, not exclusive CPU instruction cycles.
The five producer phases partition that worker exactly. Do not add them to their enclosing interrupt total.</p>
<table><tr><th>NMI frame</th><th>Total NMI</th><th>Hidden row calls</th><th>Rows/setup</th>
<th>Palette</th><th>Sprites</th><th>Tail</th><th>CHR/return</th></tr>'''+''.join(costs)+'''</table>
<p>The first three hidden producers spend approximately 120,000 clocks each on row work.
Audio publication separately costs 28,016–29,350 clocks per measured interrupt.
The complete instruction-observed replay matches the normal timeline and audio.</p>
<p>Trial patches change one guarded budget byte plus checksum only. The 16-row control is byte-identical
to the current cartridge. Original fade counters and publication deadlines are untouched.</p>
<p class="open">Full-game original-speed equivalence and the remaining physical audio gaps are still open.
This loading study does not resolve combat slowdown or certify pop-free sound.</p><p>'''+ ' · '.join(links)+'''
 · <a href="work.json">Exact calls and instruction sources</a> · <a href="manifest.json">Artifact hashes</a></p>'''
    (out/'index.html').write_text(page)
    result = dict(release_ready=False, sources=sources,
                  artifacts={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),artifacts=len(result['artifacts']),release_ready=False)))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    build(**vars(p.parse_args()))
