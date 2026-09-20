"""Bind production cached polling to the executed helper and a narrow ROM delta."""
import argparse
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.check_sprite_coordinate_patch import labels
from tools.check_joypad_poll import PREIMAGE


def audit(parent,candidate,disabled,oracle,out):
    old=(parent/'native-cpu.sfc').read_bytes();new=(candidate/'native-cpu.sfc').read_bytes()
    if old!=(disabled/'native-cpu.sfc').read_bytes():raise ValueError('Disabled cartridge differs from parent')
    a=labels(parent/'native_runtime.lbl');b=labels(candidate/'native_runtime.lbl')
    if any(b.get(k)!=v for k,v in a.items()):raise ValueError('Existing runtime symbol moved')
    qualified=json.loads((oracle/'report.json').read_text())
    if not qualified['passed'] or qualified['pad_pairs']!=65536:raise ValueError('Unqualified poll fixture')
    for p,h in qualified['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed oracle source')
    for p,h in qualified['cases'][0]['arms'][1].items():
        if sha(Path(p))!=h:raise ValueError('Changed qualified helper artifact')
    fixture=oracle/'chunk-00-1';q=labels(fixture/'runtime.lbl')['native_joypad_poll']
    body=(fixture/'runtime.bin').read_bytes()[q-0x2000:]
    if body.count(b'\x4c\xa3\xfd')!=1:raise ValueError('Ambiguous helper exit')
    body=body[:body.index(b'\x4c\xa3\xfd')+3];start=b['native_joypad_poll']
    allowed=set(range(0xffdc,0xffe0));entries=[]
    for bank in range(1,9):
        offset=bank*65536+start
        if old[offset:offset+len(body)]!=bytes([0xea])*len(body):raise ValueError('Helper overwrote occupied space')
        if new[offset:offset+len(body)]!=body:raise ValueError('Production differs from executed helper')
        allowed.update(range(offset,offset+len(body)));entries.append(bank*65536+0xfd8e)
    entries.append(0x8bd8e)
    for offset in entries:
        before=old[offset:offset+len(PREIMAGE)]
        if before[0]!=0x20 or before[9]!=0x20 or before[3:9]!=PREIMAGE[3:9] or before[12:]!=PREIMAGE[12:]:
            raise ValueError('Original translated poll loop differs')
        if new[offset:offset+3]!=b'\x4c'+start.to_bytes(2,'little'):raise ValueError('Wrong helper jump')
        allowed.update(range(offset,offset+3))
    changed={i for i,(x,y) in enumerate(zip(old,new)) if x!=y}
    if len(old)!=len(new) or not changed or not changed<=allowed:raise ValueError('Unrelated ROM changes')
    if sum(new)&65535!=int.from_bytes(new[0xffde:0xffe0],'little'):raise ValueError('Incorrect cartridge checksum')
    paths=[Path(__file__),Path('tools/check_joypad_poll.py'),Path('tools/check_sprite_coordinate_patch.py'),
        oracle/'report.json',fixture/'runtime.bin',fixture/'runtime.lbl',
        parent/'native_runtime.lbl',candidate/'native_runtime.lbl',
        *[p/'native-cpu.sfc' for p in (parent,candidate,disabled)]]
    report=dict(passed=True,changed_bytes=len(changed),helper_size=len(body),helper_address=start,
        entry_offsets=entries,preserved_global_symbols=len(a),sources={str(p):sha(p) for p in paths},
        scope='Only qualified helper in eight unused runtime areas, nine translated polling jumps and checksum differ. '
              'No relocation, original-art, mapping-table or sound-engine change; not a gameplay acceptance test.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','changed_bytes','helper_size','preserved_global_symbols')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','disabled','oracle','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
