"""Compare exact OAM copy clocks under FastROM and verify observer-neutral RAM."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

try:
    from .build_runtime_test import build,ROOT
except ImportError:
    from build_runtime_test import build,ROOT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(core,control_core,out):
    out.mkdir(parents=True,exist_ok=False)
    results={}
    for name,enabled in (('mvn',False),('word',True)):
        folder=out/name
        build(folder,oam_word_copy=enabled,oam_page=2,fastrom=True)
        syms={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (folder/'runtime.lbl').read_text().splitlines()}
        env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
        points=[f'c1{syms[s]:04x}' for s in ('@dma','@dma_copied')]
        instrument=dict(env,RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST='300',RCR_SPAN_TRACE=str(folder/'spans.csv'),
                        RCR_SPAN_PC0=points[0],RCR_SPAN_PC1=points[1])
        for label,emulator,environment in (('observed',core,instrument),('control',control_core,env)):
            subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(emulator),
                '--rom',str(folder/'adapter-test.sfc'),'--kind','adapter','--frames','300',
                '--ram',str(folder/(label+'.ram')),'--receipt',str(folder/(label+'.json'))],
                env=environment,stdout=subprocess.DEVNULL,check=True,timeout=30)
        if sha(folder/'observed.ram')!=sha(folder/'control.ram'):
            raise ValueError('Timing observer changed final WRAM')
        rows=list(csv.reader((folder/'spans.csv').open()))
        if len(rows)!=2 or any(len(r)!=16 or int(r[0])!=i or r[5]!=points[i] for i,r in enumerate(rows)):
            raise ValueError('Need exactly one linked OAM-copy entry and exit')
        clocks=int(rows[1][4])-int(rows[0][4])
        if clocks<=0:
            raise ValueError('Nonmonotonic copy clocks')
        results[name]=dict(master_clocks=clocks,observer_equivalent=True,
            source_hashes={p.name:sha(p) for p in (folder/'adapter-test.sfc',folder/'spans.csv',
                folder/'observed.json',folder/'control.json',folder/'observed.ram',folder/'runtime.lbl')})
    report=dict(passed=results['word']['master_clocks']<results['mvn']['master_clocks'],
        fastrom=True,results=results,saved_master_clocks=results['mvn']['master_clocks']-results['word']['master_clocks'],
        core_sha256=sha(core),control_core_sha256=sha(control_core),checker_sha256=sha(Path(__file__)),
        scope='One identical page-02 snapshot in the synthetic adapter, FastROM enabled. '
              'Entry-to-copy-complete elapsed clocks include intervening events. Not whole-game speed.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],saved_master_clocks=report['saved_master_clocks'],
                         clocks={k:v['master_clocks'] for k,v in results.items()}),indent=2))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','control-core','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    raise SystemExit(0 if run(a.core,a.control_core,a.out) else 1)
