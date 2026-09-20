"""Retain every dense late-palette boundary case, including any overrun failures."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from tools.check_final_batch_margin import execute
from tools.benchmark_report import sha


def audit(candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    out.mkdir(parents=True)
    cases=[dict(line=line,delay=delay,depth=1,state=state) for line in (249,250)
           for delay in range(256) for state in (0,2)]
    def run(item):
        i,c=item;root=out/f'case-{i:04}'
        try:return execute(candidate,core,root,c)
        except ValueError as e:
            if not (root/'memory.ram').exists():raise
            ram=(root/'memory.ram').read_bytes()
            return dict(case=c,failure=str(e),sampled_line=ram[0x1e1c],
                finish_line=ram[0x1c7e]+256*ram[0x1c7f],overrun_flag=ram[0x1c7b],
                artifacts={str(p):sha(p) for p in root.iterdir() if p.suffix in ('.sfc','.ram','.json')})
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(run,enumerate(cases)))
    failed=[r for r in results if 'failure' in r]
    files=[Path(__file__),Path('tools/check_final_batch_margin.py'),Path('snes/publisher_postdma_test.asm'),
        Path('snes/wram_clear.inc'),Path('tools/smoke_libretro.py'),candidate/'manifest.json',
        candidate/'native-cpu.sfc',candidate/'native_boot.lbl',core]
    report=dict(passed=not failed,cases=results,failures=failed,sources={str(p):sha(p) for p in files},
        release_ready=False,scope=__doc__+' Every integer NOP delay 0..255, targets249/250, '
        'pending palette active, state0/2, real OAM/CGRAM and overrun assertion. Not all possible CPU phases/states.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=not failed,cases=len(results),failures=len(failed),
        first_failures=[{k:v for k,v in r.items() if k!='artifacts'} for r in failed[:3]],
        latest_finish=max(r['finish_line'] for r in results))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','core','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
