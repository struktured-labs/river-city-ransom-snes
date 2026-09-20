"""Measure the executed shortcut and retain whole-loop/cadence failures."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.audit_park_instructions import parse
from tools.audit_signed_shift_game import shift_cost
from tools.benchmark_report import sha, verify_capture
from tools.build_combat_outlier_review import excerpt_bounds, outliers, context
from tools.build_saturating_shift_trial import ADDRESS, HELPER, patch
from tools.capture_combat_instructions import equivalent
from tools.combat_campaign import installed, verify_pair
from tools.review_candidate_combat import native_clip


def helper_cost(rows, first, last, image):
    calls, costs, pending = [], Counter(), None
    for i in range(first,last):
        r = rows[i]; pc = r['pc']; low = pc&65535
        if not 0xc1 <= pc>>16 <= 0xc8:
            continue
        if ADDRESS <= low < ADDRESS+17 or HELPER <= low < HELPER+64:
            if image[pc&0x3fffff] != r['opcode']:
                raise ValueError('Opcode differs from cartridge')
            costs[pc] += rows[i+1]['clock']-r['clock']
        if low == ADDRESS or (low == ADDRESS+2 and rows[i-1]['pc'] != pc-2):
            if pending is not None:
                raise ValueError('Nested shift call')
            pending = r
        elif low == ADDRESS+17 and pending is not None:
            if r['s'] != pending['s'] or pc>>16 != pending['pc']>>16:
                raise ValueError('Changed bank/stack on return')
            calls.append(dict(entry=pending, after=r, clocks=r['clock']-pending['clock']))
            pending = None
    if pending is not None or not calls:
        raise ValueError('Incomplete or missing helper calls')
    return dict(calls=calls, inclusive_clocks=sum(c['clocks'] for c in calls),
                own_instruction_clocks=sum(costs.values()))


def audit(out):
    if out.exists():
        raise ValueError('Fresh review required')
    oracle = Path('build/saturating-shift-oracle-2101/report.json')
    proof = bound_report(oracle)
    if not proof['passed']:
        raise ValueError('Failed instruction oracle')
    for p,d in proof['files'].items():
        if sha(oracle.parent/p) != d:
            raise ValueError('Changed executed oracle artifact')
    parent = Path('build/signed-shift-trial-1947')
    candidate = Path('build/saturating-school-trial-2088')
    helper = (candidate/'helper.bin').read_bytes()
    if sha(candidate/'helper.bin') != proof['files']['helper.bin']:
        raise ValueError('School trial helper differs from executed oracle')
    if patch((parent/'native-cpu.sfc').read_bytes(),helper) != (candidate/'native-cpu.sfc').read_bytes():
        raise ValueError('Trial includes unrelated changes')
    specs = [('parent',parent,Path('build/signed-shift-combat-1948'),
        Path('build/signed-shift-instruction-control-1950'),Path('build/signed-shift-school-instructions-1952'),4176),
        ('shortcut',candidate,Path('build/saturating-school-combat-2102'),
        Path('build/saturating-school-control-2105'),Path('build/saturating-school-instructions-2106'),4110)]
    paths = [Path(__file__),Path('tools/audit_signed_shift_game.py'),Path('tools/audit_park_instructions.py'),
        Path('tools/build_saturating_shift_trial.py'),Path('tools/capture_combat_instructions.py'),
        Path('tools/combat_campaign.py'),Path('tools/review_candidate_combat.py'),oracle,candidate/'helper.bin']
    runs, cards = {}, []
    out.mkdir(parents=True)
    for name,rom,root,control,capture,frame in specs:
        binding = bound_report(capture/'instruction-control.json')
        bound_report(control/'instruction-control.json')
        _,result,plain_rows,normal = verify_pair(root,'running-jumps','snes',rom)
        with installed('running-jumps'):
            receipt,timeline = verify_capture(capture)
            base,unobserved = verify_capture(control)
        equivalent(receipt,timeline,base,unobserved)
        if timeline != plain_rows or sha(control/'audio.wav') != sha(normal/'audio.wav'):
            raise ValueError('Instruction and main-observer controls differ')
        trace = Path(receipt['instruction_trace']['path'])
        if sha(trace) != receipt['instruction_trace']['sha256']:
            raise ValueError('Changed instruction trace')
        with trace.open() as stream:
            rows = parse(csv.reader(stream),binding['first'],binding['last'])
        loop = next(l for l in result['iterations'] if l['start']['frame']==frame)
        first,last = [next(i for i,r in enumerate(rows) if r['clock']==loop[k]['clock']) for k in ('start','finish')]
        if rows[first]['pc'] != loop['start']['pc'] or rows[last]['pc'] != loop['finish']['pc']:
            raise ValueError('Loop boundary PC mismatch')
        image = (rom/'native-cpu.sfc').read_bytes()
        shifts = (shift_cost if name=='parent' else helper_cost)(rows,first,last,image)
        costs = Counter()
        for a,b in zip(rows[first:last],rows[first+1:last+1]):
            costs[f'{a["pc"]:06x}'] += b['clock']-a['clock']
        total = rows[last]['clock']-rows[first]['clock']
        if sum(costs.values()) != total:
            raise ValueError('Incomplete elapsed clock partition')
        runs[name] = dict(loop=loop,strict_passed=result['passed'],elapsed_master_clocks=total,
            shift=shifts,top_instruction_elapsed=costs.most_common(30),
            all_outliers=[context(v['loop'],timeline) for v in outliers(result['iterations'],timeline)])
        cards.append(f'<h2>{name}: {frame}–{loop["finish"]["frame"]}</h2><p>{total:,} elapsed clocks. Strict gate: {result["passed"]}.</p><div class="grid">')
        for f in (frame,frame+1,loop['finish']['frame'],loop['finish']['frame']+7):
            source = normal/f'frames/frame-{f:05d}.png'
            if sha(source) != timeline[f-1]['frame_image_sha256']:
                raise ValueError('Changed source image')
            dest = f'{name}-{f}.png'; shutil.copyfile(source,out/dest); paths.append(source)
            cards.append(f'<figure><img src="{dest}"><figcaption>Frame {f}</figcaption></figure>')
        _,_,a,b = excerpt_bounds(timeline,frame,loop['finish']['frame'])
        runs[name]['audio'] = native_clip(normal/'audio.wav',out/(name+'.wav'),a,b)
        cards.append(f'</div><audio controls src="{name}.wav"></audio>')
        paths.extend((rom/'native-cpu.sfc',rom/'manifest.json',capture/'capture.json',
            capture/'instruction-control.json',control/'capture.json',control/'instruction-control.json',
            trace,normal/'audio.wav',root/'running-jumps-snes-observed/combat-observer.json',
            normal/'combat-observer.json'))
    report = dict(runs=runs,oracle_passed=True,observer_neutral=True,deployed=False,release_ready=False,
        sources={str(p):sha(p) for p in paths},
        scope='Same-input independent replays, not identical encounters or equal-work NES proof. '
        'Exact instruction endpoints; elapsed clocks include interrupts/DMA. Every cadence outlier retained. '
        'Older scheduling branch isolates this patch and remains rejected; newer branch is tested separately.')
    page = '<!doctype html><meta charset="utf-8"><title>Signed-shift saturation</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}.grid{display:grid;grid-template-columns:repeat(4,1fr)}img,audio{width:100%}figure{margin:8px}</style>'
    page += '<h1>School-return shortcut: measured saving, strict failure retained</h1><p>'+html.escape(report['scope'])+'</p>'
    page += '<p><a href="report.json">Full instruction costs and outliers</a> · <a href="../saturating-combat-review-2108/">Newer scheduling: both combat policies</a> · <a href="../saturating-entry-2107/">NES room-entry comparisons</a></p>'+''.join(cards)
    (out/'index.html').write_text(page)
    report['artifacts'] = {p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:dict(total=v['elapsed_master_clocks'],shift=v['shift']['inclusive_clocks'],calls=len(v['shift']['calls'])) for k,v in runs.items()}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    audit(**vars(p.parse_args()))
