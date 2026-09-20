"""Execute experimental sweep metadata through real generic/direct/fused CPU paths."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.check_direct_apu import case as direct
from tools.check_sound_commit import case as fused


def check(core,out):
    paths=[Path(p) for p in ('tools/check_sweep_producer.py','tools/check_direct_apu.py',
        'tools/check_sound_commit.py','tools/build_sweep_packet.py','tools/build_native.py',
        'snes/sweep_events.inc','snes/native_runtime.asm','snes/direct_apu.inc',
        'snes/sound_commit.inc','snes/direct_apu_test.asm','snes/native_boot.asm')]+[core]
    sources={str(p):sha(p) for p in paths}
    out.mkdir(parents=True,exist_ok=False)
    addresses=list(range(0x4000,0x4014))+[0x4015,0x4017,0x4018,0x4020]
    jobs=[addresses[i:i+6] for i in range(0,len(addresses),6)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        direct_results=list(pool.map(lambda args:direct(core,out/f'direct-{args[0]}',args[1],
            sweep_events=True),enumerate(jobs)))
    fused_results=[]
    for channel in range(8):
        # Y<32 mirrors the actual source shadow. Music retains Y; effects mask
        # it to 0..15. Muted music must not emit an event at all.
        for first in range(0,32,8):
            rows=[(0x40,value,(value^0xc5)|0x30,15,(value*19^0xa5)&255,
                   value>>4,channel,register,mute)
                  for register in range(first,first+8) for value in (0,1,7,8,127,128,254,255)
                  for mute in (0,128)]
            fused_results.append(fused(core,out/f'fused-{channel}-{first}',rows,sweep_events=True))
    mutations=[]
    for label,mutation in (
        ('lost_direct_event',('    jsr sweep_track_write','    nop\n    nop\n    nop')),
        ('wrong_event_register',('    jsr sweep_track_write','    inx\n    jsr sweep_track_write\n    dex'))):
        try:direct(core,out/label,[0x4001,0x4002,0x4005,0x4006],range(8),mutation,sweep_events=True)
        except ValueError as error:mutations.append(dict(name=label,detected=True,error=str(error)))
        else:raise ValueError('Executed mutation survived: '+label)
    for path,digest in sources.items():
        if sha(Path(path))!=digest:raise ValueError('Source changed during execution: '+path)
    report=dict(passed=True,direct_cases=sum(r['cases'] for r in direct_results),
        fused_cases=sum(r['cases'] for r in fused_results),direct=direct_results,fused=fused_results,
        mutations=mutations,sources=sources,release_ready=False,
        scope='Actual generic/direct/fused 65C816 paths with independent packet/ABI expectations. '
        'All byte values on generic/direct addresses; eight sampled values, all shadow slots, '
        'music/effects and suppression on fused paths. Event metadata only; not SPC receipt, '
        'clock generation, synthesized audio or gameplay/hardware performance.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','direct_cases','fused_cases','mutations')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    check(**vars(p.parse_args()))
