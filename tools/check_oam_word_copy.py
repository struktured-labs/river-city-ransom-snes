"""Execute low-WRAM OAM source pages, stack/self copies, fallback and mutations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

try:
    from .build_runtime_test import build,ROOT
except ImportError:
    from build_runtime_test import build,ROOT

PAGES=(*range(32),32,255)


def run(core,out,fastrom=False):
    out.mkdir(parents=True,exist_ok=False)
    results=[]
    command=[sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
             '--kind','adapter','--frames','300']
    for page in PAGES:
        folder=out/f'page-{page:02x}'
        build(folder,oam_word_copy=True,oam_page=page,fastrom=fastrom)
        completed=subprocess.run(command+['--rom',str(folder/'adapter-test.sfc'),
            '--receipt',str(folder/'receipt.json')],capture_output=True,text=True,timeout=30)
        (folder/'execution.log').write_text(completed.stdout+completed.stderr)
        if completed.returncode:
            raise RuntimeError(f'OAM page {page:02x} failed: {completed.stderr}')
        results.append(dict(page=page,receipt_sha256=hashlib.sha256((folder/'receipt.json').read_bytes()).hexdigest()))
    mutations=[]
    for name,page,old,new in (
        ('missing-first-word',2,bytes.fromhex('a5008f00107e'),bytes.fromhex('a500eaeaeaea')),
        ('wrong-source-word',2,bytes.fromhex('a5008f00107e'),bytes.fromhex('a5028f00107e')),
        ('missing-wram-boundary',32,None,None)):
        parent=out/f'page-{page:02x}'
        image=(parent/'adapter-test.sfc').read_bytes()
        if old is None:
            symbols={s.split()[2].lstrip('.'):int(s.split()[1],16) for s in (parent/'runtime.lbl').read_text().splitlines()}
            old=bytes.fromhex('c9200090034c')+symbols['@dma_mvn'].to_bytes(2,'little')
            new=bytes.fromhex('c9ff0090034c')+symbols['@dma_mvn'].to_bytes(2,'little')
        if image.count(old)!=8:
            raise ValueError(f'Cannot locate exactly eight {name} mutations')
        mutant=out/(name+'.sfc');mutant.write_bytes(image.replace(old,new))
        completed=subprocess.run(command+['--rom',str(mutant)],capture_output=True,text=True,timeout=30)
        (out/(name+'.log')).write_text(completed.stdout+completed.stderr)
        if not completed.returncode or 'WRAM status=ee, adapter case=6' not in completed.stderr:
            raise RuntimeError(f'{name} did not fail OAM data/ABI case 6')
        mutations.append(dict(name=name,sha256=hashlib.sha256(mutant.read_bytes()).hexdigest(),expected_case=6))
    report=dict(passed=True,pages=results,negative_controls=mutations,fastrom=fastrom,
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='256-byte snapshot and caller A/X/Y/DB/D for all 32 low-WRAM pages, plus high-page MVN fallback. '
              'Includes active stack and self-copy source pages. Not whole-game speed or hardware fidelity.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,pages=len(results),negative_controls=len(mutations))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--fastrom',action='store_true')
    a=p.parse_args();run(a.core,a.out,a.fastrom)
