"""Exact FastROM alias-copy span, with normal-core full-WRAM controls."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

try:
    from .check_alias_words import case, ROOT
except ImportError:
    from check_alias_words import case, ROOT


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run(core,control,out):
    out.mkdir(parents=True,exist_ok=False)
    results={}
    for label,enabled in (('mvn',False),('word',True)):
        folder=out/label
        case(control,folder,0,0,1,word_copy=enabled,fastrom=True)
        symbols={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (folder/'test.lbl').read_text().splitlines()}
        points=[f'c0{symbols[k]:04x}' for k in ('prepare_row_alias','alias_return')]
        env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
        env.update(RCR_SPAN_TRACE=str(folder/'spans.csv'),RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST='300',
                   RCR_SPAN_PC0=points[0],RCR_SPAN_PC1=points[1])
        subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
            '--rom',str(folder/'test.sfc'),'--kind','adapter','--frames','300','--ram',str(folder/'observed.ram'),
            '--receipt',str(folder/'observed.json')],check=True,capture_output=True,env=env,timeout=30)
        if sha(folder/'observed.ram')!=sha(folder/'memory.ram'):
            raise ValueError('Alias timing observer changed full WRAM')
        rows=list(csv.reader((folder/'spans.csv').open()))
        if len(rows)!=2 or any(len(r)!=16 or int(r[0])!=i or r[5]!=points[i] for i,r in enumerate(rows)):
            raise ValueError('Missing exact linked alias entry/return')
        clocks=int(rows[1][4])-int(rows[0][4])
        if clocks<=0:raise ValueError('Nonmonotonic clock')
        results[label]=dict(master_clocks=clocks,full_wram_observer_equivalent=True,
            files={p.name:sha(p) for p in folder.iterdir() if p.suffix in ('.json','.sfc','.ram','.csv','.lbl')})
    report=dict(passed=results['word']['master_clocks']<results['mvn']['master_clocks'],results=results,
        saved_master_clocks=results['mvn']['master_clocks']-results['word']['master_clocks'],
        core_sha256=sha(core),control_core_sha256=sha(control),checker_sha256=sha(Path(__file__)),
        scope='One vertical row-0 dirty alias snapshot and return, FastROM active. Exact elapsed master clocks include events. '
              'Both arms have byte-identical full-WRAM observer controls; not a whole-game speed ratio.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],clocks={k:v['master_clocks'] for k,v in results.items()},saved=report['saved_master_clocks'])))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','control','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();raise SystemExit(0 if run(a.core,a.control,a.out) else 1)
