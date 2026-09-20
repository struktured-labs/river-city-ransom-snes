"""Prove the appended coordinate helper does not relocate unrelated production code."""
import argparse
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.check_sprite_coordinates import PREIMAGE
from tools.check_sprite_position import PREIMAGE as POSITION_PREIMAGE


def labels(path):
    return {r.split()[2].lstrip('.'):int(r.split()[1],16) for r in path.read_text().splitlines()
            if not r.split()[2].startswith('.@')}


def check(parent,candidate,disabled,oracle,out,position=False):
    helper_name='native_sprite_position' if position else 'native_sprite_coordinates'
    size=56 if position else 33
    preimage=POSITION_PREIMAGE if position else PREIMAGE
    pc=0xeeee if position else 0xef11
    patch_size=4 if position else 3
    a=(parent/'native-cpu.sfc').read_bytes();b=(candidate/'native-cpu.sfc').read_bytes()
    if a!=(disabled/'native-cpu.sfc').read_bytes():raise ValueError('Disabled source changed parent cartridge')
    old=labels(parent/'native_runtime.lbl');new=labels(candidate/'native_runtime.lbl')
    if any(new.get(k)!=v for k,v in old.items()):raise ValueError('Existing global runtime symbol moved')
    start=new[helper_name]
    ref=oracle/'chunk-00-1';rl=labels(ref/'test.lbl');fixture=(ref/'test.sfc').read_bytes()
    helper=fixture[rl[helper_name]:rl[helper_name]+size]
    if len(helper)!=size or helper[-3:]!=bytes.fromhex('4c26ef'):raise ValueError('Wrong qualified helper')
    qualified=json.loads((oracle/'report.json').read_text())
    if not qualified['passed'] or qualified['offset_pairs' if position else 'low_byte_pairs']!=65536:raise ValueError('Unqualified arithmetic matrix')
    for p,h in qualified['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed arithmetic source')
    for p,h in qualified['cases'][0]['arms'][1].items():
        if sha(Path(p))!=h:raise ValueError('Changed qualified helper artifact')
    allowed=set(range(0xffdc,0xffe0));entries=[]
    for bank in range(1,9):
        offset=bank*65536+start
        if a[offset:offset+size]!=bytes([0xea])*size or b[offset:offset+size]!=helper:
            raise ValueError('Helper overwrites live code or differs from qualified body')
        allowed.update(range(offset,offset+size));entries.append(bank*65536+pc)
    entries.append(0x80000+pc-0x4000) # selected PRG pair repeats the last fixed bank
    for offset in entries:
        wanted=b'\x4c'+start.to_bytes(2,'little')+(b'\xea' if position else b'')
        if a[offset:offset+len(preimage)]!=preimage or b[offset:offset+patch_size]!=wanted:
            raise ValueError('Wrong original loop or entry patch')
        allowed.update(range(offset,offset+patch_size))
    changes={i for i,(x,y) in enumerate(zip(a,b)) if x!=y}
    if len(a)!=len(b) or not changes or not changes<=allowed:raise ValueError('Unrelated cartridge changes')
    if sum(b)&65535!=int.from_bytes(b[0xffde:0xffe0],'little'):raise ValueError('Wrong cartridge checksum')
    paths=[Path(__file__),Path('tools/check_sprite_position.py' if position else 'tools/check_sprite_coordinates.py'),oracle/'report.json',
        ref/'test.sfc',ref/'test.lbl',parent/'native_runtime.lbl',candidate/'native_runtime.lbl',
        *[p/'native-cpu.sfc' for p in (parent,candidate,disabled)]]
    report=dict(passed=True,changed_bytes=len(changes),helper_address=start,entry_offsets=entries,
        preserved_global_symbols=len(old),sources={str(p):sha(p) for p in paths},
        scope='Only nine mirrored entry jumps, eight copies of the qualified helper in unused padding, '
              'and checksum differ. All prior global runtime symbols remain fixed. Not game or audio acceptance.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,changed_bytes=len(changes),preserved_global_symbols=len(old))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','disabled','oracle','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--position',action='store_true')
    check(**vars(p.parse_args()))
