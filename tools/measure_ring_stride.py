"""Instruction clocks of exact oracle cartridges, with same-core observation controls."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols


def audit(oracle,parent,core,out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):raise ValueError('Fresh isolated execution required')
    proof=bound_report(oracle/'report.json')
    if not proof['passed']:raise ValueError('Unqualified oracle')
    entry=symbols(parent/'native_runtime.lbl')['bulk_ring_bytes']
    out.mkdir(parents=True);results=[];sources=dict(proof['sources'])
    #20-byte vertical tile command and a crossing command, both real oracle cases.
    for index in (0,8):
        record=proof['cases'][index];case=record['case'];arms={}
        for arm in ('before','after'):
            rom=oracle/f'case-{index:03}'/arm/'test.sfc'
            if record['artifacts'].get(str(rom))!=sha(rom):raise ValueError('Changed fixture')
            sources[str(rom)]=sha(rom)
            for observed in (False,True):
                folder=out/f'{index}-{arm}-{observed}';folder.mkdir()
                env=os.environ.copy();trace=folder/'instructions.csv'
                if observed:env.update(RCR_INSTRUCTION_TRACE=str(trace.resolve()),RCR_PROFILE_FIRST='1',RCR_PROFILE_LAST='5')
                subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),'--rom',str(rom),
                    '--kind','adapter','--frames','120','--ram',str(folder/'memory.ram'),
                    '--receipt',str(folder/'receipt.json')],env=env,check=True,capture_output=True,text=True,timeout=30)
                if not observed:normal=(folder/'memory.ram').read_bytes();continue
                if normal!=(folder/'memory.ram').read_bytes():raise ValueError('Observer changed complete fixture RAM')
                rows=list(csv.reader(trace.open()))
                starts=[i for i,r in enumerate(rows) if int(r[4],16)==case['BANK']*65536+entry]
                if len(starts)!=1:raise ValueError('Missing/ambiguous tested invocation')
                start=starts[0];image=rom.read_bytes()
                end=next(i for i in range(start+1,len(rows)) if image[(int(rows[i][4],16)&0x3fffff):
                    (int(rows[i][4],16)&0x3fffff)+4]==bytes.fromhex('8f00607e'))
                arms[arm]=dict(entry=rows[start],after_return=rows[end],clocks=int(rows[end][3])-int(rows[start][3]),
                              instructions=end-start)
        results.append(dict(case=case,arms=arms,saved_clocks=arms['before']['clocks']-arms['after']['clocks']))
    sources.update({str(p):sha(p) for p in (Path(__file__),oracle/'report.json',parent/'native_runtime.lbl',
        core,Path('tools/smoke_libretro.py'),Path('tools/snes9x_instruction_trace.inc'),Path('.deps/snes9x/cpuexec.cpp'))})
    report=dict(cases=results,observer_neutral=True,sources=sources,
        artifacts={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
        scope='One exact actual-runtime call per fixture, entry through caller return; complete same-core RAM neutral. '
              'Elapsed master clocks, not a combat-frame recovery or full-game speed claim.',release_ready=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(results))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('oracle','parent','core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
