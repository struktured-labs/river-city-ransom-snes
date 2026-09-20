"""Fail-closed companion/menu/equipment prototype audit, not a release gate."""
import argparse
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha,verify_capture
from tools.capture_ai_p2 import installed


def phase_samples(rows,states,name,skip=3):
    return [(bytes.fromhex(r['game_ram_hex']),bytes.fromhex(s))
            for r,s in zip(rows,states) if r['phase']==name][skip:]


def evaluate(rows,states,equipment=False,disabled=False,seed=None):
    if len(rows)!=len(states) or not rows:raise ValueError('Missing state coverage')
    samples=lambda name:phase_samples(rows,states,name)
    checks={'no_adapter_fault':not any(r['fault'] for r in rows),
            'physical_p1_inputs_delivered':all(r['input_requested']==r['input_delivered'] for r in rows)}
    if disabled:
        # Power-on WRAM is arbitrary until original reset's DMA clear. Begin
        # at the authenticated visible menu, before any opt-in/game input.
        ready=[(r,bytes.fromhex(s)) for r,s in zip(rows,states) if r['phase']!='boot_to_menu']
        checks['default_off']=bool(ready) and all(s[0]==0 and s[3]==0 for r,s in ready)
        checks['no_synthetic_p2']=bool(ready) and all(bytes.fromhex(r['game_ram_hex'])[0xf1]==0 for r,s in ready)
        return checks
    checks['settings_toggle_debounced']=bool(samples('toggle_release')) and all(s[0]==1 for r,s in samples('toggle_release'))
    for name in ('manage_selector','manage_belongings','reacquire_menu'):
        rr=samples(name)
        checks[name+'_exclusive_p2']=bool(rr) and all(s[3]==2 and r[0xf0]&~0x10==0 for r,s in rr)
    rr=samples('release_inside_menu')
    checks['release_in_menu_keeps_ai_suspended']=bool(rr) and all(s[3]==0 and r[0x3f]&0x20 for r,s in rr)
    if not equipment:
        rr=samples('ai_follow')
        checks['p2_follow_moves']=bool(rr) and rr[-1][0][0x389]+256*rr[-1][0][0x391]>rr[0][0][0x389]+256*rr[0][0][0x391]
        rr=samples('ai_encounter')
        checks['p2_attacks_autonomously']=bool(rr) and any(r[0xf1]&0x80 for r,s in rr)
        checks['ai_never_start_select']=all(r[0xf1]&0x30==0 for name in ('ai_follow','ai_encounter','ai_resume') for r,s in samples(name))
    else:
        if not seed:raise ValueError('Missing explicit fixture initialization')
        rr=samples('p2_equipment_complete')
        final=rr[-1][0] if rr else bytes(2048)
        checks['p2_old_shoes_unequipped_new_shoes_equipped']=final[0x655:0x657]==bytes([0x21,0xa2])
        checks['p2_original_equipment_stats']=list(final[i] for i in (0x4a4,0x4b0))==[25,45]
        after=[bytes.fromhex(r['game_ram_hex']) for r in rows if r['frame']>=seed['frame_before']]
        checks['p1_inventory_and_equipment_stats_untouched']=bool(after) and all(
            r[0x64d:0x655].hex()==seed['p1_inventory'] and [r[0x4a3],r[0x4af]]==seed['p1_stats'] for r in after)
        checks['original_item_owner_is_p2']=final[0x59d]==1
    rr=samples('ai_resume')
    checks['exit_restores_p1_and_ai']=bool(rr) and all(s[3]==1 and not r[0x3f]&0x20 and r[0xf0]==2 for r,s in rr)
    return checks


def review(normal,equipment,disabled,candidate,out):
    if out.exists():raise ValueError('Fresh report required')
    results={};sources={};cards=[];out.mkdir(parents=True)
    for name,folder,eq,off in [('input-only',normal,False,False),('seeded-equipment',equipment,True,False),('default-off',disabled,False,True)]:
        detail=json.loads((folder/'ai-p2.json').read_text())
        for p,digest in detail['sources'].items():
            if sha(Path(p))!=digest:raise ValueError('Changed capture dependency: '+p)
        with installed(not off,eq):receipt,rows=verify_capture(folder)
        if not receipt['capture_complete'] or receipt['rom_sha256']!=sha(candidate/'native-cpu.sfc'):
            raise ValueError('Wrong/incomplete ROM capture')
        states=json.loads((folder/'ai-state.json').read_text())
        checks=evaluate(rows,states,eq,off,detail['synthetic_equipment_seed'])
        results[name]=dict(checks=checks,passed=all(checks.values()),frames=len(rows),
            synthetic_seed=detail['synthetic_equipment_seed'])
        sources.update(detail['sources']);sources[str(folder/'ai-p2.json')]=sha(folder/'ai-p2.json')
        for phase in (['manage_belongings','p2_boat_shoes_selected','p2_equipment_complete','ai_resume'] if eq else
                      ['ai_follow','ai_encounter','manage_belongings','ai_resume']):
            src=folder/(phase+'.png');dest=name+'-'+phase+'.png';shutil.copy2(src,out/dest)
            sources[str(src)]=sha(src)
            cards.append(f'<figure><img src="{dest}"><figcaption>{name}: {phase}</figcaption></figure>')
    paths=[Path(__file__),Path('tests/test_ai_p2.py'),Path('snes/ai_p2.asm'),
           Path('snes/ai_p2.cfg'),Path('tools/build_ai_p2.py'),candidate/'manifest.json',candidate/'native-cpu.sfc']
    sources.update({str(p):sha(p) for p in paths})
    report=dict(results=results,passed=all(r['passed'] for r in results.values()),sources=sources,
        release_ready=False,physical_verified=False,original_speed_verified=False,
        scope='Initial in-ROM opt-in P2 companion. Input-only follow/attack/menu demo plus clearly '
              'synthetic five-byte inventory/stat initialization for original equipment logic. '
              'No progression redesign or XP. No physical P2 override proof, hardware or whole-game qualification.')
    table=''.join(f'<h2>{name}</h2><ul>'+''.join(f'<li>{key}: {value}</li>' for key,value in result['checks'].items())+'</ul>' for name,result in results.items())
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>AI-assisted P2 prototype</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1250px;margin:2em auto}a{color:cyan}'
        '.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}figure{margin:0}img{width:100%;image-rendering:pixelated}</style>'
        '<h1>AI-assisted P2: experimental, offline only</h1><p>Select original 2P and tap R in pregame settings '
        'to enable. Hold controller1 L to manage P2; Start retains original global pause. Release L restores '
        'P1 with a neutral handoff. AI stays suspended while menus are open.</p><p><strong>Equipment test is synthetic:</strong> '
        'five bytes initialize P1 Loafers and P2 worn Sneakers + Boat Shoes with correct prior bonuses. '
        'Controller1 then makes the original game unequip Sneakers/equip Boat Shoes. P1 must remain unchanged.</p>'
        '<p>No MiSTer deployment. No XP or progression changes. Pathfinding, friendly-fire avoidance, clear on-screen '
        'AI indicator, preset compatibility and broader encounters remain unfinished.</p><a href="report.json">Hash-bound audit</a>'+table+
        '<div class="grid">'+''.join(cards)+'</div>')
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(results,indent=2))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('normal','equipment','disabled','candidate','out'):p.add_argument('--'+k,type=Path,required=True)
    raise SystemExit(0 if review(**vars(p.parse_args())) else 1)
