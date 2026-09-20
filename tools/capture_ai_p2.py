"""Small input-only AI P2 demonstration; one physical controller, no RAM writes."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
import ctypes as C
import json
from pathlib import Path

from tools import benchmark_capture as benchmark
from tools.benchmark_report import sha, verify_capture


def scenario(enabled=True, equipment=False):
    phases=deepcopy(benchmark.SCENARIO[:11])
    phases[2:2]=[dict(name='choose_2p',frames=6,buttons=['Down']),
                 dict(name='release_2p',frames=12)]
    at=next(i for i,p in enumerate(phases) if p['name']=='start_game')
    phases[at:at]=[dict(name='toggle_ai',frames=12,buttons=['R'] if enabled else []),
                   dict(name='toggle_release',frames=30)]
    tail=[
        dict(name='ai_follow',frames=100,buttons=['Right']),
        dict(name='ai_encounter',frames=180),
        dict(name='manage_start',frames=12,buttons=['L','Start']),
        dict(name='manage_selector',frames=90,buttons=['L']),
        dict(name='manage_belongings_open',frames=12,buttons=['L','A']),
        dict(name='manage_belongings',frames=180,buttons=['L']),
        dict(name='release_inside_menu',frames=30),
        dict(name='reacquire_menu',frames=12,buttons=['L']),
        dict(name='manage_cancel',frames=12,buttons=['L','B']),
        dict(name='manage_selector_again',frames=120,buttons=['L']),
        dict(name='manage_close',frames=12,buttons=['L','Start']),
        dict(name='manage_closed',frames=60,buttons=['L']),
        dict(name='management_release',frames=30),
        dict(name='ai_resume',frames=100,buttons=['Left']),
    ]
    if equipment:
        tail=tail[2:]
        at=next(i for i,p in enumerate(tail) if p['name']=='manage_cancel')
        tail[at:at]=[
            dict(name='p2_choose_boat_shoes',frames=12,buttons=['L','Down']),
            dict(name='p2_boat_shoes_selected',frames=30,buttons=['L']),
            dict(name='p2_equip',frames=12,buttons=['L','A']),
            dict(name='p2_equip_animation',frames=300,buttons=['L']),
            dict(name='p2_advance',frames=12,buttons=['L','A']),
            dict(name='p2_equipped',frames=180,buttons=['L']),
            dict(name='p2_advance_defense',frames=12,buttons=['L','A']),
            dict(name='p2_equipment_complete',frames=360,buttons=['L']),
        ]
    return phases+tail


@contextmanager
def installed(enabled,equipment=False):
    old=benchmark.scenario_for
    name='ai-p2-equipment' if equipment else 'ai-p2-on' if enabled else 'ai-p2-off'
    benchmark.scenario_for=lambda n:scenario(enabled,equipment) if n==name else old(n)
    try:yield name
    finally:benchmark.scenario_for=old


@contextmanager
def observe(core_path,records,seed=None):
    original=C.CDLL
    loaded=[]
    def library(name,*args,**kwargs):
        core=original(name,*args,**kwargs)
        if not isinstance(name,str) or Path(name).resolve()!=core_path.resolve():return core
        loaded.append(name)
        run=core.retro_run
        core.retro_get_memory_data.argtypes=[C.c_uint]
        core.retro_get_memory_data.restype=C.c_void_p
        def execute():
            if seed is not None and not seed:
                ptr=core.retro_get_memory_data(2)
                if ptr:
                    ram=C.string_at(ptr,0x20000)
                    if ram[0x1f000]==1 and ram[0x100]==0xc0 and ram[0x692]==4 and not ram[0x3f]&0x20:
                        changes={0x64d:0x23,0x655:0xa1,0x656:0x22,
                                 0x4a4:ram[0x4a4]+10,0x4b0:ram[0x4b0]+20}
                        if any(v>255 for v in changes.values()):raise ValueError('Invalid fixture stats')
                        for at,value in changes.items():C.memmove(ptr+at,bytes([value]),1)
                        seed.update(frame_before=len(records)+1,
                            changes={hex(at):dict(before=ram[at],after=value) for at,value in changes.items()},
                            p1_inventory=bytes([0x23])+ram[0x64e:0x655],
                            p1_stats=[ram[0x4a3],ram[0x4af]],
                            p2_stats_before=[ram[0x4a4]+10,ram[0x4b0]+20])
            run()
            ptr=core.retro_get_memory_data(2)
            if not ptr:raise ValueError('Missing WRAM')
            records.append(C.string_at(ptr+0x1f000,16).hex())
        core.retro_run=execute
        return core
    C.CDLL=library
    try:
        yield
        if len(loaded)!=1:raise ValueError('Wrong selected core')
    finally:C.CDLL=original


def capture(candidate,core,out,disabled=False,equipment=False):
    if equipment and disabled:raise ValueError('Equipment fixture requires enabled AI')
    enabled=not disabled
    records=[]
    refs={'menu':(Path('build/reference-title-05'),600),
          'settings':(Path('build/reference-walk-02'),600),
          'story':(Path('build/reference-walk-02'),900),
          'street':(Path('build/reference-walk-02'),1800)}
    files=[Path(__file__),Path(benchmark.__file__),Path('tools/benchmark_report.py'),
        Path('tools/smoke_libretro.py'),candidate/'manifest.json',candidate/'native-cpu.sfc',core]
    sources={str(p):sha(p) for p in files}
    seed={} if equipment else None
    with installed(enabled,equipment) as name,observe(core,records,seed):
        benchmark.capture(core,candidate/'native-cpu.sfc','snes',refs,out,name,False,True)
        receipt,rows=verify_capture(out)
    if len(records)!=len(rows):raise ValueError('Missing private-state coverage')
    if any(sha(Path(p))!=digest for p,digest in sources.items()):raise ValueError('Changed sources')
    (out/'ai-state.json').write_text(json.dumps(records)+'\n')
    summary={}
    for phase in scenario(enabled,equipment):
        rr=[(r,bytes.fromhex(s)) for r,s in zip(rows,records) if r['phase']==phase['name']]
        summary[phase['name']]=dict(frames=len(rr),enabled=sorted({s[0] for r,s in rr}),
            modes=sorted({s[3] for r,s in rr}),targets=sorted({s[4] for r,s in rr}),
            held=sorted({bytes.fromhex(r['game_ram_hex'])[0xf0:0xf2].hex() for r,s in rr}),
            end_positions=[[bytes.fromhex(r['game_ram_hex'])[0x388+i]+
                256*bytes.fromhex(r['game_ram_hex'])[0x390+i] for i in (0,1)] for r,s in rr[-1:]])
    sources.update({str(out/n):sha(out/n) for n in ('capture.json','ai-state.json')})
    if seed is not None:
        if not seed:raise ValueError('Equipment fixture never seeded')
        seed['p1_inventory']=seed['p1_inventory'].hex()
    report=dict(enabled_requested=enabled,summary=summary,sources=sources,synthetic_equipment_seed=seed,
        capture_complete=receipt['capture_complete'],faults=[r['frame'] for r in rows if r['fault']],
        release_ready=False,physical_tested=False,
        scope=('Synthetic equipment fixture: five documented original-game RAM bytes seeded once; '
               'all subsequent actions are controller1 inputs. ' if equipment else __doc__)+
              ' Original full RAM/phase PNGs retained. Observed RAM reads are after retro_run; '
              'mode values are diagnostics, not alone proof of equipment modification.')
    (out/'ai-p2.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','core','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--disabled',action='store_true')
    p.add_argument('--equipment',action='store_true')
    capture(**vars(p.parse_args()))
