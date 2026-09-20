"""Audit ordinary-input waypoint arrival and unchanged strict café menu oracles."""
import argparse
import html
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

try:
    from .benchmark_report import verify_capture,sha
    from . import check_shop_repeat as repeat
    from . import check_shop_choice_no as choice
except ImportError:
    from benchmark_report import verify_capture,sha
    import check_shop_repeat as repeat
    import check_shop_choice_no as choice

CAFE_REGIONS=((8,136,80,184),(96,64,248,168),(8,192,248,216))


def cafe_identity(reference,folder):
    expected=np.asarray(Image.open(reference/'observe_shop.png').convert('RGB'))>>3
    actual=np.asarray(Image.open(folder/'observe_shop.png').convert('RGB'))>>3
    return [dict(region=list(r),mismatch_pixels=int(np.any(
        expected[r[1]:r[3],r[0]:r[2]]!=actual[r[1]:r[3],r[0]:r[2]],axis=2).sum())) for r in CAFE_REGIONS]


def build(reference,candidate,cafe_reference,out,negative=None):
    folders={'nes':reference,'snes':candidate}
    if negative is not None:
        folders['negative']=negative
    base,_=verify_capture(cafe_reference)
    if base['system']!='nes' or not base['capture_complete']:
        raise ValueError('Need authenticated original café identity reference')
    receipts={}
    for name,folder in folders.items():
        r,rows=verify_capture(folder)
        if (r['system']!=('nes' if name=='nes' else 'snes') or not r['capture_complete']
                or r['scenario_name'] not in ('traversal-waypoint-shop-repeat','traversal-waypoint-shop-no')
                or r['templates']['menu']['source_rom']!=base['rom_sha256']
                or any(x['fault'] or x['input_requested']!=x['input_delivered'] for x in rows)):
            raise ValueError('Incomplete/faulted or unbound waypoint replay')
        receipts[name]=r
    if len({r['scenario_sha256'] for r in receipts.values()})!=1:
        raise ValueError('Different waypoint/menu scenarios')
    identities={name:cafe_identity(cafe_reference,folder) for name,folder in folders.items()}
    if any(any(x['mismatch_pixels'] for x in results) for results in identities.values()):
        raise ValueError('Café name, item list or ready dialogue does not match original')
    oracle=repeat if receipts['nes']['scenario_name'].endswith('repeat') else choice
    result=oracle._analyze(reference,candidate)
    old=oracle._analyze(reference,negative) if negative else None
    report=dict(passed=result['passed'] and (old is None or not old['passed']),
        menu=result,negative_control=old,cafe_identity=identities,
        captures={name:dict(path=str(folder),sha256=sha(folder/'capture.json'),
                           rom_sha256=receipts[name]['rom_sha256'],
                           waypoints=[dict(name=s['name'],frames=s['frames'],matched=s['transition_matched'])
                                      for s in receipts[name]['segments'] if s['name'] in ('reach_mall','enter_cafe')])
                  for name,folder in folders.items()},
        sources=dict(cafe_reference_sha256=sha(cafe_reference/'capture.json'),
                     audit_sha256=sha(Path(__file__)),oracle_sha256=sha(Path(oracle.__file__))),
        scope='Identical deterministic navigation policy, independently observed state and delivered inputs. '
              'Café identity is matched to authenticated original NES pixels before applying the unchanged '
              'fixed-region menu oracle. Navigation durations/inputs may differ: NOT a same-input speed benchmark '
              'or hardware/audio-fidelity verdict.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    display=repeat.DISPLAY_PHASES if oracle is repeat else choice.DISPLAY
    cards=[]
    for phase in ('observe_shop',*display):
        cards.append('<h2>'+html.escape(phase)+'</h2>')
        for name,folder in folders.items():
            target=f'{name}-{phase}.png'
            shutil.copyfile(folder/f'{phase}.png',out/target)
            cards.append(f'<figure><figcaption>{name}</figcaption><img src="{target}"></figure>')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Waypoint café regression</title>
<style>body{background:#111820;color:#eee;font:16px system-ui;margin:30px}figure{display:inline-block}
img{width:384px;image-rendering:pixelated}a{color:#9cf}</style>'''+
        f'<h1>Waypoint café regression: {"PASS" if report["passed"] else "FAIL"}</h1><p>'+html.escape(report['scope'])+
        '</p><p><a href="report.json">Checks, route decisions and hashes</a></p>'+''.join(cards))
    print(json.dumps(dict(passed=report['passed'],menu_passed=result['passed'],
                         negative_rejected=old is not None and not old['passed']),indent=2))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','candidate','cafe-reference','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--negative',type=Path)
    a=p.parse_args()
    raise SystemExit(0 if build(a.reference,a.candidate,a.cafe_reference,a.out,a.negative) else 1)
