"""Execute real ring-cache bytes, compare full WRAM, and independently check writes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.check_ring_stride import execute, independent


def audit(parent, candidate, core, reference, out):
    if out.exists():
        raise ValueError('Fresh output required')
    proof = bound_report(reference/'report.json')
    if not proof['passed']:
        raise ValueError('Unqualified source cases')
    meta = json.loads((candidate/'manifest.json').read_text())
    sources = dict(meta['experimental_ring_dirty_cache']['sources'])
    for name,digest in sources.items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed candidate source')
    for root in (parent,candidate):
        if sha(root/'native-cpu.sfc') != json.loads((root/'manifest.json').read_text())['rom_sha256']:
            raise ValueError('Changed ROM')
    cases = [r['case'] for r in proof['cases']]
    # Preserve old case ordering for the independent clock measurement tool.
    cases += [dict(r,STRIDE=0) for r in cases if r['STRIDE']==4]
    out.mkdir(parents=True)
    def check(item):
        i,case = item
        folder = out/f'case-{i:03}'
        old = execute(parent,core,folder/'before',case)
        new = execute(candidate,core,folder/'after',case)
        if len(old) != 131072 or len(new) != 131072:
            raise ValueError('Incomplete WRAM')
        excluded = set(range(0x100,0x200)) | {0x1c62,0x1c63}
        mismatch = [n for n,(a,b) in enumerate(zip(old,new)) if a != b and n not in excluded]
        if mismatch:
            raise ValueError('Full RAM mismatch '+str((i,case,mismatch[:20])))
        checked = independent(new,case)
        return dict(case=case,independent_oracle=checked,artifacts={str(p):sha(p)
            for p in folder.rglob('*') if p.suffix in ('.sfc','.ram','.json')})
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(check,enumerate(cases)))
    wrong = execute(candidate,core,out/'wrong-stride',cases[0],True)
    try:
        independent(wrong,cases[0])
    except ValueError:
        rejected = True
    else:
        raise ValueError('Wrong stride survived independent oracle')
    paths = [Path(__file__),Path('tools/check_ring_stride.py'),Path('snes/ring_stride_test.asm'),
             Path('snes/wram_clear.inc'),Path('tools/smoke_libretro.py'),core,reference/'report.json',
             *[root/name for root in (parent,candidate) for name in
               ('manifest.json','native-cpu.sfc','native_runtime.lbl')]]
    sources.update({str(p):sha(p) for p in paths})
    report = dict(passed=True,cases=results,mutant_rejected=rejected,sources=sources,
        mutant_artifacts={str(p):sha(p) for p in (out/'wrong-stride').iterdir()
                          if p.suffix in ('.sfc','.ram','.json')},
        scope=__doc__+' Only dead stack and fixture heartbeat excluded. No whole-game claim.',
        release_ready=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(results),
                         independent=sum(r['independent_oracle'] for r in results))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','core','reference','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
