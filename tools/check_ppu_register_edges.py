"""Additional unchanged-CHR, unusual scroll latch and wrapping byte-stack cases."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.check_ppu_register import execute,independent


def audit(parent,candidate,core,oracle,out):
    if out.exists():
        raise ValueError('Fresh output required')
    proof = bound_report(oracle/'report.json')
    if not proof['passed'] or proof['sources'].get(str(candidate/'native-cpu.sfc')) != sha(candidate/'native-cpu.sfc'):
        raise ValueError('Different candidate')
    cases = []
    for value in (0,1,8,16,24,127,128,255):
        for difference in (0,4,0x80):
            cases.append(dict(ADDRESS=0x2000,VALUE=value,OLD_CTRL=value^difference,LATCH=0))
    for latch in (0,1,2,3,127,128,254,255):
        for value in (0,1,255):
            cases.append(dict(ADDRESS=0x2005,VALUE=value,OLD_CTRL=0,LATCH=latch))
    for i,case in enumerate(cases):
        case.update(FLAGS=(0x35,0x75,0x3d,0x7d)[i%4],BANK=0xc1+i%8,STACK=(3,4,5,6,9,255)[i%6])
    out.mkdir(parents=True)
    def check(item):
        i,case = item
        folder = out/f'case-{i:03}'
        old = execute(parent,core,folder/'before',case)
        new = execute(candidate,core,folder/'after',case)
        excluded = set(range(0x100,0x200)) | {0x1c62,0x1c63}
        if len(old)!=131072 or len(new)!=131072 or any(a!=b and n not in excluded for n,(a,b) in enumerate(zip(old,new))):
            raise ValueError('Full WRAM/ABI edge mismatch: '+str(case))
        if not independent(new,case):
            raise ValueError('Missing independent edge oracle')
        return dict(case=case,artifacts={str(p):sha(p) for p in folder.rglob('*') if p.suffix in ('.sfc','.ram','.json')})
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(check,enumerate(cases)))
    paths = [Path(__file__),Path('tools/check_ppu_register.py'),Path('snes/ppu_register_test.asm'),
             core,oracle/'report.json',parent/'native-cpu.sfc',candidate/'native-cpu.sfc']
    sources = {**proof['sources'],**{str(p):sha(p) for p in paths}}
    report = dict(passed=True,cases=results,sources=sources,scope=__doc__,release_ready=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(results))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','core','oracle','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
