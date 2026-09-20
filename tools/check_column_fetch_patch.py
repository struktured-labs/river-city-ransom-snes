"""Bind the production column helper to executed fixture bytes and a narrow patch."""
import argparse
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.check_column_fetch import PREIMAGE
from tools.check_sprite_coordinate_patch import labels


def audit(parent,candidate,disabled,oracle,out):
    old=(parent/'native-cpu.sfc').read_bytes();new=(candidate/'native-cpu.sfc').read_bytes()
    if old!=(disabled/'native-cpu.sfc').read_bytes():raise ValueError('Disabled build differs')
    a=labels(parent/'native_runtime.lbl');b=labels(candidate/'native_runtime.lbl')
    if any(b.get(k)!=v for k,v in a.items()):raise ValueError('Existing symbol moved')
    q=json.loads((oracle/'report.json').read_text())
    if not q['passed'] or q['cases']!=5120:raise ValueError('Unqualified helper')
    for p,h in q['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed qualification source')
    for p,h in q['chunks'][0]['arms'][1].items():
        if sha(Path(p))!=h:raise ValueError('Changed executed helper')
    fixture=oracle/'chunk-000-1';symbols=labels(fixture/'test.lbl')
    start=symbols['native_column_fetch'];end=symbols['interrupt']
    body=(fixture/'test.bin').read_bytes()[start-0x8000:end-0x8000]
    if not body or body[-3:]!=bytes.fromhex('4ce3c2'):raise ValueError('Wrong helper extent')
    address=b['native_column_fetch'];allowed=set(range(0xffdc,0xffe0));entries=[]
    for bank in range(1,9):
        offset=bank*65536+address
        if old[offset:offset+len(body)]!=bytes([0xea])*len(body):raise ValueError('Helper overwrote code')
        if new[offset:offset+len(body)]!=body:raise ValueError('Production helper differs')
        allowed.update(range(offset,offset+len(body)));entries.append(bank*65536+0xc2c3)
    entries.append(0x882c3)
    for offset in entries:
        if old[offset:offset+len(PREIMAGE)]!=PREIMAGE:raise ValueError('Original column block differs')
        if new[offset:offset+3]!=b'\x4c'+address.to_bytes(2,'little'):raise ValueError('Wrong entry jump')
        allowed.update(range(offset,offset+3))
    changed={i for i,(a,b) in enumerate(zip(old,new)) if a!=b}
    if len(old)!=len(new) or not changed or not changed<=allowed:raise ValueError('Unrelated ROM changes')
    if sum(new)&65535!=int.from_bytes(new[0xffde:0xffe0],'little'):raise ValueError('Wrong checksum')
    paths=[Path(__file__),Path('tools/check_column_fetch.py'),Path('tools/check_sprite_coordinate_patch.py'),
        oracle/'report.json',fixture/'test.bin',fixture/'test.lbl',
        parent/'native_runtime.lbl',candidate/'native_runtime.lbl',
        *[p/'native-cpu.sfc' for p in (parent,candidate,disabled)]]
    report=dict(passed=True,changed_bytes=len(changed),helper_size=len(body),preserved_symbols=len(a),
        sources={str(p):sha(p) for p in paths},scope='Only nine entry jumps, eight exact qualified helpers '
        'in unused padding and checksum differ. Not full-game speed, graphics or audio qualification.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','changed_bytes','helper_size','preserved_symbols')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','disabled','oracle','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
