"""Bind compact-index game bytes to the executed VRAM oracle and patch scope."""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.build_hidden_index_trial import assemble, labels


def changed_scope(before,after,start,end):
    if len(before)!=2097152 or len(before)!=len(after) or not 0x8000<start<end<0xffc0:
        raise ValueError('Unexpected image size or helper extent')
    changed=[i for i,(a,b) in enumerate(zip(before,after)) if a!=b]
    if not changed or any(not(start<=i<end or 0xffdc<=i<0xffe0) for i in changed):
        raise ValueError('Unrelated or missing changes')
    checksum=int.from_bytes(after[0xffde:0xffe0],'little')
    complement=int.from_bytes(after[0xffdc:0xffde],'little')
    if sum(after)&65535!=checksum or checksum^complement!=65535:
        raise ValueError('Wrong cartridge checksum')
    return changed


def audit(parent,candidate,oracle,out):
    report=json.loads((oracle/'report.json').read_text())
    if not report['passed'] or len(report['cases'])!=6144 or len(report['mutants'])!=5:
        raise ValueError('Need complete compact-index oracle and mutants')
    for path,digest in report['sources'].items():
        if sha(Path(path))!=digest:raise ValueError('Changed oracle source')
    old,new=(labels(p/'native_boot.lbl') for p in (parent,candidate))
    start,end=old['prepare_hidden_direct_row'],old['prepare_palette']
    before,after=((p/'native-cpu.sfc').read_bytes() for p in (parent,candidate))
    changed=changed_scope(before,after,start,end)
    # ca65 local names (e.g. @done) repeat in different scopes; a name-keyed
    # dictionary cannot prove their preservation after replacing one scope.
    def outside_symbols(path):
        return Counter((r.split()[2],int(r.split()[1],16)) for r in path.read_text().splitlines()
                       if not start<=int(r.split()[1],16)<end)
    if outside_symbols(parent/'native_boot.lbl')!=outside_symbols(candidate/'native_boot.lbl'):
        raise ValueError('Unrelated boot symbol moved')
    if (parent/'native_runtime.lbl').read_bytes()!=(candidate/'native_runtime.lbl').read_bytes():
        raise ValueError('Game runtime symbols changed')
    out.mkdir(parents=True,exist_ok=False)
    disabled,_=assemble(out/'disabled',start,end-start,False)
    enabled,_=assemble(out/'enabled',start,end-start,True)
    if disabled!=before[start:end] or enabled!=after[start:end]:
        raise ValueError('Production helper differs from verified assembly')
    fixture=oracle/'case-0000'
    receipt=report['cases'][0]
    if sha(fixture/'test.sfc')!=receipt['rom_sha256'] or sha(fixture/'memory.ram')!=receipt['ram_sha256']:
        raise ValueError('Executed oracle fixture changed')
    symbols=labels(fixture/'test.lbl')
    a,b=symbols['prepare_hidden_direct_row'],symbols['prepare_palette']
    relocated,_=assemble(out/'fixture-address',a,b-a,True)
    if relocated!=(fixture/'test.sfc').read_bytes()[a:b]:
        raise ValueError('Oracle does not execute the same relocated helper')
    paths=[Path(__file__),Path('tools/build_hidden_index_trial.py'),oracle/'report.json',
           candidate/'manifest.json',*[p/'native-cpu.sfc' for p in (parent,candidate)],
           *[p/'native_boot.lbl' for p in (parent,candidate)],fixture/'test.sfc',fixture/'memory.ram',
           fixture/'test.lbl',*[out/p/'helper.bin' for p in ('disabled','enabled','fixture-address')]]
    result=dict(passed=True,changed_bytes=len(changed),old_helper_bytes=end-start,
        disabled_matches_parent=True,relocated_oracle_matches=True,sources={str(p):sha(p) for p in paths},
        scope='Only hidden-row helper bytes and checksum differ. All outside boot/runtime labels retained. '
              'The exact newly assembled helper at fixture addresses matches bytes executed by the '
              '6144-case VRAM oracle. This does not qualify full-game timing or audio.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sources','scope')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','oracle','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
