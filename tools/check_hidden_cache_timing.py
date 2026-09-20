"""Paired equal-output timing of actual cached and uncached row producers."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.check_hidden_high_cache import case,ROOT
from tools.benchmark_report import sha


def run(core,observer,out,direct_pair=False,compact_index=False):
    if direct_pair and compact_index:
        raise ValueError('Select only one experiment')
    out.mkdir(parents=True,exist_ok=False)
    sources=[Path(__file__),ROOT/'tools/check_hidden_high_cache.py',ROOT/'tools/check_rows.py']
    sources += [ROOT/'snes'/name for name in ('hidden_high_cache_test.asm','native_prepare.asm',
        'hidden_direct_rows.inc','hidden_direct_probe_setup.inc','hidden_direct_probe_readback.inc')]
    hashes={str(p):sha(p) for p in sources}
    samples=[]
    for start,mirror,half in ((0,0,0),(1,0,16),(28,0,0),(60,0,16),(0,1,16),(28,1,0),(124,1,16),(127,0,0)):
        arms={};outputs=[]
        for name,enabled in (('before',False),('after',True)):
            folder=out/f'{start}-{mirror}-{half}-{name}'
            receipt=case(core,folder,start=start,mirror=mirror,half=half,
                enabled=True if direct_pair or compact_index else enabled, direct_pair=direct_pair and enabled,
                dirty_alias=direct_pair, budget=12 if direct_pair else 10,
                compact_index=compact_index and enabled)
            labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (folder/'test.lbl').read_text().splitlines()}
            points=[f'c0{labels[k]:04x}' for k in ('native_prepare','prepare_palette')]
            env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
            env.update(RCR_SPAN_TRACE=str(folder/'spans.csv'),RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST='120',
                       RCR_SPAN_PC0=points[0],RCR_SPAN_PC1=points[1])
            subprocess.run([sys.executable,'tools/smoke_libretro.py','--core',str(observer),'--rom',str(folder/'test.sfc'),
                '--kind','adapter','--frames','120','--ram',str(folder/'observed.ram'),
                '--receipt',str(folder/'observed.json')],env=env,capture_output=True,check=True,timeout=30)
            if sha(folder/'observed.ram')!=receipt['ram_sha256']:raise ValueError('Observer changed result')
            with (folder/'spans.csv').open() as f:rows=list(csv.reader(f))
            if len(rows)!=2 or any(len(r)!=16 or int(r[0])!=i or r[5]!=points[i] for i,r in enumerate(rows)):
                raise ValueError('Missing exact linked stage boundaries')
            clocks=int(rows[1][4])-int(rows[0][4])
            if clocks<=0:raise ValueError('Nonmonotonic clocks')
            ram=(folder/'memory.ram').read_bytes()
            outputs.append(tuple(ram[a:b] for a,b in ((0x8000,0xa000),(0x3000,0x5000),(0x1d00,0x1d80),
                (0x1e80,0x1f00),(0x12000,0x13000))))
            arms[name]=dict(clocks=clocks,oracle=receipt,spans_sha256=sha(folder/'spans.csv'),
                           observed_receipt_sha256=sha(folder/'observed.json'))
        if outputs[0]!=outputs[1]:raise ValueError('Changed delivered graphics or queue ownership')
        samples.append(dict(start=start,mirror=mirror,half=half,arms=arms,
                            saved_clocks=arms['before']['clocks']-arms['after']['clocks']))
    if hashes!={str(p):sha(p) for p in sources}:raise ValueError('Timing sources changed')
    report=dict(passed=all(s['saved_clocks']>0 for s in samples),samples=samples,sources=hashes,
        direct_pair=direct_pair,compact_index=compact_index,
        core_sha256=sha(core),observer_sha256=sha(observer),scope=(
        'Paired ten-row-budget original/compact-index preparation stages. ' if compact_index else
        'Paired twelve-row-budget scalar/paired-DMA stages, all aliases dirty. ' if direct_pair else
        'Paired ten-row-budget uncached/cached preparation stages. ')+
        'with identical actual VRAM, staging, ownership and source; both arms pass independent pixel-word oracle. '
        'Observer RAM exactly equals normal run. Not full-game speed or audio timing.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],savings=[s['saved_clocks'] for s in samples])))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','observer','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--direct-pair',action='store_true')
    p.add_argument('--compact-index',action='store_true')
    raise SystemExit(0 if run(**vars(p.parse_args())) else 1)
