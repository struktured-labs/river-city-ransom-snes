"""Audit actual shop amounts, repeat/cap behavior and the opt-in final-result hold."""
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from tools.benchmark_report import sha,verify_capture
from tools import capture_shop_qol_amounts as amounts
from tools.capture_shop_qol_feedback import installed as dense
from tools.capture_shop_qol_hold import installed as hold


def load(folder,adapter):
    report=json.loads((folder/'shop-qol-amounts.json').read_text());sources={}
    extras=[folder/'shop-qol-amounts.json']
    if adapter:extras.append(folder/('shop-qol-'+adapter+'.json'))
    for extra in extras:
        obj=json.loads(extra.read_text())
        for p,digest in obj['sources'].items():
            if sha(Path(p))!=digest:raise ValueError('Changed source '+p)
            sources[p]=digest
        sources[str(extra)]=sha(extra)
    context=dense if adapter=='feedback' else hold if adapter=='hold' else None
    if context:
        with context(report['case']):
            with amounts.scenario(report['case']):receipt,rows=verify_capture(folder)
    else:
        with amounts.scenario(report['case']):receipt,rows=verify_capture(folder)
    if not receipt['capture_complete'] or any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in rows):
        raise ValueError('Incomplete/faulted capture')
    snapshots={}
    for snap in report['snapshots']:
        phase=snap['phase'];ram=(folder/(phase+'.ram')).read_bytes()
        actual={name:ram[0x49f+i*4] for i,name in enumerate(amounts.STATS)}
        text=amounts.decode_tiles((folder/(phase+'.nametable')).read_bytes())
        if snap['p1']!=actual or snap['dialogue_lines']!=text:raise ValueError('Summary differs from bound RAM/text')
        snapshots[phase]=snap
    return report,snapshots,rows,sources


def pixels(path):return np.asarray(Image.open(path).convert('RGB'))[192:216,8:248]>>3


def build(out):
    if out.exists():raise ValueError('Fresh output required')
    configs={
        'nes_tea':('shop-qol-teacap-feedback-nes-02','feedback'),
        'snes_tea':('shop-qol-teacap-feedback-snes-02','feedback'),
        'nes_coffee':('shop-qol-coffee-nes-01',None),
        'snes_coffee':('shop-qol-coffee-snes-01',None),
        'nes_pancakes':('shop-qol-pancakes-feedback-nes-01','feedback'),
        'snes_pancakes':('shop-qol-pancakes-feedback-snes-01','feedback'),
        'held_tea':('shop-qol-teacap-hold-snes-03','hold'),
        'held_pancakes':('shop-qol-pancakes-hold-snes-01','hold'),
        'failed_unpolled':('shop-qol-teacap-hold-snes-01','feedback'),
    }
    loaded={};sources={}
    for label,(name,adapter) in configs.items():
        loaded[label]=load(Path('build')/name,adapter);sources.update(loaded[label][3])
    out.mkdir();cards=[];observations=[];gates={}
    for label in ('nes_tea','snes_tea'):
        r,snaps,rows,_=loaded[label]
        progression=[snaps[f'food_{i}_wait_0']['p1']['will'] for i in range(13)]
        gates[label+'_natural_cap']=progression==[min(63,19+4*i) for i in range(13)]
        matching=[x for name,x in snaps.items() if name.startswith('food_0_wait_0_sample')
                  and x['dialogue_lines'][1]=='WILL POWER   4 Up.']
        observations.append(dict(label=label,natural_will_progression=progression,
            complete_message_checkpoint_frames=[x['frame'] for x in matching],checkpoint_spacing=4,
            sampled_duration_estimate_frames=len(matching)*4,
            caveat='Four-frame sampling bounds duration; not exact every-frame text timing.'))
    for label,stat,amount in [('nes_coffee','will',2),('snes_coffee','will',2),
                              ('nes_pancakes','stamina',32),('snes_pancakes','stamina',25)]:
        _,snaps,_,_=loaded[label]
        before=snaps['food_0_before'];after=snaps['food_0_wait_0']
        gates[label+'_numeric_delta']=after['p1'][stat]-before['p1'][stat]==amount and str(amount) in after['dialogue_lines'][1]
        observations.append(dict(label=label,first_message=after['dialogue_lines'][1],
            actual_delta=after['p1'][stat]-before['p1'][stat]))
    held_results=[]
    for label,baseline in [('held_tea','snes_tea'),('held_pancakes','snes_pancakes')]:
        r,snaps,rows,_=loaded[label];spec=r['spec'];base=loaded[baseline][1]
        for i in range(spec['purchases']):
            result=snaps[f'food_{i}_held_result'];returned=snaps[f'food_{i}_returned']
            wait=snaps[f'food_{i}_wait_{spec["advances"]-1}'];text=result['dialogue_lines'][1]
            matches=[x for x in base.values() if x['dialogue_lines'][1]==text]
            if not matches:raise ValueError('No original numeric text reference for '+text)
            original=matches[0]
            source=Path('build')/configs[baseline][0]/(original['phase']+'.png')
            candidate=Path('build')/configs[label][0]/(result['phase']+'.png')
            mismatch=int(np.any(pixels(source)!=pixels(candidate),axis=2).sum())
            original_after=base[f'food_{i}_wait_{spec["advances"]-1}']
            good=(text==wait['dialogue_lines'][1] and returned['shop_state']==8
                  and result['p1']==returned['p1']==original_after['p1']
                  and result['money']==returned['money']==original_after['money']
                  and result['item_id']==spec['item_id'] and mismatch==0)
            held_results.append(dict(case=label,purchase=i+1,text=text,
                result_frame=result['frame'],returned_frame=returned['frame'],
                dialogue_held_last_120_frames=text==wait['dialogue_lines'][1],
                stat_and_money_match_untouched_parent=result['p1']==original_after['p1'] and result['money']==original_after['money'],
                reference_phase=original['phase'],dialogue_pixel_mismatches=mismatch,passed=good))
            if i in (0,1,spec['purchases']-1):
                name=f'{label}-{i}.png';shutil.copy2(candidate,out/name)
                cards.append(f'<figure><figcaption>{label}, purchase {i+1}: {text}</figcaption><img src="{name}"></figure>')
        first=snaps[f'food_0_advance_{spec["advances"]-1}']
        gates[label+'_held_button_not_dismissed']=first['dialogue_lines'][1]==snaps['food_0_held_result']['dialogue_lines'][1]
    gates['all_actual_amounts_preserved_and_dismissals_work']=all(x['passed'] for x in held_results)
    failed=loaded['failed_unpolled'][1]
    gates['unpolled_negative_cannot_complete_repeat_purchases']=failed['food_12_wait_0']['p1']['will']==19
    for p in (Path(__file__),Path('tests/test_shop_qol_hold.py'),
              Path('build/shop-qol-final-hold-02/manifest.json')):sources[str(p)]=sha(p)
    manifest=json.loads(Path('build/shop-qol-final-hold-02/manifest.json').read_text())
    for p,digest in manifest['experimental_shop_final_hold']['sources'].items():
        if sha(Path(p))!=digest:raise ValueError('Changed builder input')
        sources[p]=digest
    report=dict(schema='rcr-shop-qol-final-hold-review-v1',passed=all(gates.values()),gates=gates,
        observations=observations,held_results=held_results,sources=sources,
        artifacts={p.name:sha(p) for p in out.glob('*.png')},
        candidate='build/shop-qol-final-hold-02/native-cpu.sfc',candidate_sha256=manifest['rom_sha256'],
        release_ready=False,hardware_tested=False,
        scope='15 ordinary-input final-result confirmations (13 Tea including natural cap, 2 Pancakes). '
              'P1 runtime only; P2 and statless branches have assembled-helper control-flow fixtures, '
              'not full P2 shop execution. Music remains captured but acoustic fidelity not certified. '
              'Repeated actual amounts/economy preserved versus same parent. No marker or preview UI.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Shop numeric result hold</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}'
        'figure{display:inline-block;margin:8px}img{width:384px;image-rendering:pixelated}a{color:#8df}</style>'
        '<h1>Keep the actual shop bonus visible</h1>'
        '<p>The original game already prints numeric results, including repeat gains and capped recovery. '
        'But its final result disappears quickly: Tea’s complete +4 line occupies four 4-frame checkpoints '
        '(roughly 16 frames). The opt-in candidate holds the existing final text until a fresh confirmation.</p>'
        '<p>15 purchases tested: 13 Tea purchases naturally reach Will63, including a capped purchase; '
        'two Pancakes purchases preserve actual recovery and Max Power gains. Holding the original '
        'advance button does not dismiss; release and fresh confirmation return to the item list.</p>'
        '<p>No balance, equipment, item prices, new glyphs, or duplicate notifications. '
        'Not deployed or release-ready; full P2 shop execution remains unqualified.</p>'
        '<p><a href="report.json">Hashes, retained failed variant, numeric/pixel/return gates</a></p>'
        +''.join(cards))
    print(json.dumps(dict(passed=report['passed'],gates=gates,output=str(out)),indent=2))
    return report['passed']


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    raise SystemExit(0 if build(p.parse_args().out) else 1)
