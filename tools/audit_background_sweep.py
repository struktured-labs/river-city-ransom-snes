"""Compare actual background planes at unchanged first-stable camera samples.

Primary-frame differences remain visible. No pixel masks or sample realignment.
Requires full primary timeline/PCM neutrality against independent normal cores.
"""
import argparse
import html
import json
from pathlib import Path
import shutil

try:
    from .benchmark_report import verify_capture,sha
    from .audit_scroll_sweep import observations,ROOMS,MIN_COMMON
    from .audit_scroll_publication import mismatch,frame_path,BACKGROUND_REGION
    from .background_oracle_report import verify as verify_oracle
except ImportError:
    from benchmark_report import verify_capture,sha
    from audit_scroll_sweep import observations,ROOMS,MIN_COMMON
    from audit_scroll_publication import mismatch,frame_path,BACKGROUND_REGION
    from background_oracle_report import verify as verify_oracle

PLAYFIELD=(0,32,256,192)


def neutral(observed,normal):
    receipt,rows=observed;other,baseline=normal
    return (receipt['system']==other['system'] and receipt['rom_sha256']==other['rom_sha256']
        and receipt['scenario_sha256']==other['scenario_sha256']
        and receipt['audio_sha256']==other['audio_sha256']
        and [{k:v for k,v in r.items() if k!='background'} for r in rows]==baseline)


def background_path(root,row,region=PLAYFIELD):
    value=row.get('background',{})
    flags=bytes.fromhex(value.get('valid_lines',''))
    if len(flags)!=240 or not all(flags[region[1]:region[3]]):
        return None
    path=root/value['image']
    if sha(path)!=value['sha256']:raise ValueError('Background image changed')
    return path


def analyze(reference,candidate,a,b):
    a_first,a_stable,_=observations(a[1],True)
    b_first,b_stable,late=observations(b[1],True)
    common=sorted(a_stable.keys()&b_stable.keys())
    rows=[]
    for key in common:
        ra,rb=a_stable[key],b_stable[key]
        pa,pb=background_path(reference,ra),background_path(candidate,rb)
        supported=pa is not None and pb is not None
        primary,_=mismatch(frame_path(reference,ra),frame_path(candidate,rb),BACKGROUND_REGION)
        narrow=mismatch(pa,pb,BACKGROUND_REGION)[0] if supported else None
        wide=mismatch(pa,pb,PLAYFIELD)[0] if supported else None
        rows.append(dict(room=key[0],camera=key[1],nes_frame=ra['frame'],snes_frame=rb['frame'],
            supported=supported,primary_band_differences=primary,background_band_differences=narrow,
            background_playfield_differences=wide,nes_settle=ra['frame']-a_first[key]['frame'],
            snes_settle=rb['frame']-b_first[key]['frame']))
    coverage={str(room):sum(k[0]==room for k in common) for room in ROOMS}
    gates=dict(both_complete=a[0]['capture_complete'] and b[0]['capture_complete'],
        all_rooms_at_least_64=all(v>=MIN_COMMON for v in coverage.values()),
        no_faults=not any(r['fault'] for r in a[1]+b[1]),
        all_selected_rows_supported=bool(rows) and all(r['supported'] for r in rows),
        background_band_exact=bool(rows) and all(r['background_band_differences']==0 for r in rows),
        expanded_background_playfield_exact=bool(rows) and all(r['background_playfield_differences']==0 for r in rows),
        no_late_publications=not late,
        stable_no_later=bool(rows) and all(r['snes_settle']<=r['nes_settle'] for r in rows))
    return dict(passed=all(gates.values()),gates=gates,coverage=coverage,comparisons=rows,late_publications=late)


def audit(reference,candidate,normal_reference,normal_candidate,oracle,out,negative=None):
    folders=dict(nes=reference,snes=candidate,normal_nes=normal_reference,normal_snes=normal_candidate)
    if negative:folders['negative']=negative
    data={name:verify_capture(folder) for name,folder in folders.items()}
    for name,(receipt,rows) in data.items():
        if (receipt['system']!=('nes' if name in ('nes','normal_nes') else 'snes') or
            any(r['input_requested']!=r['input_delivered'] for r in rows)):
            raise ValueError('Wrong system or undelivered input')
        if name in ('nes','snes','negative') and not receipt.get('background_observer'):
            raise ValueError('Missing bound background observer')
    if len({r['scenario_sha256'] for r,_ in data.values()})!=1:
        raise ValueError('Mismatched scenarios')
    verify_oracle(oracle,data['snes'][0]['core_sha256'])
    if negative and data['negative'][0]['core_sha256']!=data['snes'][0]['core_sha256']:
        raise ValueError('Negative control uses an unqualified observer core')
    result=analyze(reference,candidate,data['nes'],data['snes'])
    result['gates'].update(nes_observer_neutral=neutral(data['nes'],data['normal_nes']),
                           snes_observer_neutral=neutral(data['snes'],data['normal_snes']))
    if negative:
        control=analyze(reference,negative,data['nes'],data['negative'])
        result['negative']=control
        # Incompleteness by itself is not a sensitivity proof.
        result['gates']['real_broken_scroll_detected']=bool(control['late_publications']) or any(
            (r['background_band_differences'] or 0)>0 for r in control['comparisons'])
    result['passed']=all(result['gates'].values())
    result.update(sources={name:dict(capture_sha256=sha(folder/'capture.json'),
        rom_sha256=data[name][0]['rom_sha256']) for name,folder in folders.items()},
        oracle_sha256=sha(oracle),audit_sha256=sha(Path(__file__)),
        oracle_verifier_sha256=sha(Path(__file__).with_name('background_oracle_report.py')),
        scope='First second-consecutive post-fade camera observations, identical to the primary-image sweep. '
        'Actual background plane without OBJ composition, fixed RGB555 bands y=32..79 and y=32..191. '
        'Primary images are never altered or realigned. Independent normal-core timelines and PCM must match. '
        'Not actor/combat speed, room-entry timing, whole-game or acoustic certification.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    cards=[]
    for row in result['comparisons']:
        if (row['primary_band_differences'] or row['background_playfield_differences'] or
            not row['supported'] or row['camera'] in (0,64,128,255,256,384,511)):
            cards.append(f'<h2>Room {row["room"]}, camera {row["camera"]}</h2><p>Primary band: '
                f'{row["primary_band_differences"]}; background band: {row["background_band_differences"]}; '
                f'expanded background: {row["background_playfield_differences"]}</p><section>')
            for label,frame in (('nes',row['nes_frame']),('snes',row['snes_frame'])):
                sample=data[label][1][frame-1]
                for plane,path in (('primary',frame_path(folders[label],sample)),
                                   ('background',folders[label]/sample['background']['image'])):
                    name=f'{label}-{row["room"]}-{row["camera"]}-{plane}.png'
                    shutil.copyfile(path,out/name)
                    cards.append(f'<figure><img loading="lazy" src="{name}"><figcaption>{label} {plane}, frame {frame}</figcaption></figure>')
            cards.append('</section>')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Background scrolling audit</title>'
        '<style>body{background:#101821;color:#eee;font:17px system-ui;max-width:1200px;margin:30px auto}'
        'a{color:#9df}section{display:grid;grid-template-columns:1fr 1fr}figure{margin:8px}'
        'img{width:512px;image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>Background sweep: '+('PASS' if result['passed'] else 'FAIL')+'</h1><p>'+html.escape(result['scope'])+
        '</p><a href="report.json">All comparisons, source hashes, and negative control</a><pre>'+
        html.escape(json.dumps(dict(gates=result['gates'],coverage=result['coverage']),indent=2))+'</pre>'+''.join(cards))
    print(json.dumps(dict(passed=result['passed'],gates=result['gates'],coverage=result['coverage']),indent=2))
    return result['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','candidate','normal-reference','normal-candidate','oracle','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--negative',type=Path)
    a=p.parse_args()
    raise SystemExit(0 if audit(a.reference,a.candidate,a.normal_reference,a.normal_candidate,a.oracle,a.out,a.negative) else 1)
