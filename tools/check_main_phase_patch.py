"""Bind the phase wrapper to executed bytes and exactly two known relocations."""
import argparse
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.check_sprite_coordinate_patch import labels


def audit(parent,candidate,disabled,oracle,out):
    old=(parent/'native-cpu.sfc').read_bytes();new=(candidate/'native-cpu.sfc').read_bytes()
    if old!=(disabled/'native-cpu.sfc').read_bytes():raise ValueError('Disabled build differs')
    a=labels(parent/'native_runtime.lbl');b=labels(candidate/'native_runtime.lbl')
    if any(b.get(k)!=v for k,v in a.items()):raise ValueError('Existing runtime symbol moved')
    q=json.loads((oracle/'report.json').read_text());manifest=json.loads((candidate/'manifest.json').read_text())
    if not q['passed'] or len(q['cases'])!=50 or q['phase']!=manifest['experimental_main_phase_line']:
        raise ValueError('Wrong qualified phase')
    for p,h in q['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed oracle source')
    for p,h in q['cases'][0]['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed qualified fixture')
    fixture=oracle/'case-000'
    raw=[r.split() for r in (fixture/'test.lbl').read_text().splitlines()]
    s=labels(fixture/'test.lbl');high=[int(r[1],16) for r in raw if r[2]=='.@high']
    if len(high)!=1:raise ValueError('Ambiguous helper end')
    begin=s['gameplay_phase_start'];end=high[0]+2
    body=bytearray((fixture/'test.bin').read_bytes()[begin-0x8000:end-0x8000])
    if body[:3]!=bytes.fromhex('084820') or body[5:8]!=bytes.fromhex('68284c') or body[-3:]!=bytes.fromhex('606860'):
        raise ValueError('Wrong wrapper opcodes or extent')
    if int.from_bytes(body[3:5],'little')!=s['gameplay_phase_wait'] or int.from_bytes(body[8:10],'little')!=s['gameplay_iteration_start']:
        raise ValueError('Unexpected fixture relocation')
    body[3:5]=b['gameplay_phase_wait'].to_bytes(2,'little')
    body[8:10]=b['gameplay_iteration_start'].to_bytes(2,'little')
    address=b['gameplay_phase_start'];allowed=set(range(0xffdc,0xffe0));entries=[]
    for bank in range(1,9):
        offset=bank*65536+address
        if old[offset:offset+len(body)]!=bytes([0xea])*len(body):raise ValueError('Overwrote existing code')
        if new[offset:offset+len(body)]!=body:raise ValueError('Production differs from relocated qualified helper')
        allowed.update(range(offset,offset+len(body)));entries.append(bank*65536+0xf27d)
    entries.append(0x8b27d)
    for offset in entries:
        if old[offset:offset+5]!=b'\x4c'+a['gameplay_iteration_start'].to_bytes(2,'little')+b'\xea\xea':
            raise ValueError('Wrong parent entry')
        if new[offset:offset+5]!=b'\x4c'+address.to_bytes(2,'little')+b'\xea\xea':
            raise ValueError('Wrong phase entry')
        allowed.update(range(offset,offset+3))
    changed={i for i,(a,b) in enumerate(zip(old,new)) if a!=b}
    if len(old)!=len(new) or not changed or not changed<=allowed:raise ValueError('Unrelated changes')
    if sum(new)&65535!=int.from_bytes(new[0xffde:0xffe0],'little'):raise ValueError('Wrong checksum')
    paths=[Path(__file__),Path('tools/check_sprite_coordinate_patch.py'),oracle/'report.json',
        fixture/'test.bin',fixture/'test.lbl',parent/'native_runtime.lbl',candidate/'native_runtime.lbl',
        candidate/'manifest.json',*[p/'native-cpu.sfc' for p in (parent,candidate,disabled)]]
    report=dict(passed=True,phase=q['phase'],changed_bytes=len(changed),helper_size=len(body),
        preserved_symbols=len(a),sources={str(p):sha(p) for p in paths},
        scope='Only nine entry redirects, eight copies of the qualified wrapper with two verified relocations, '
              'and checksum differ. Not speed, latency or audio qualification.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','phase','changed_bytes','helper_size','preserved_symbols')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','disabled','oracle','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
