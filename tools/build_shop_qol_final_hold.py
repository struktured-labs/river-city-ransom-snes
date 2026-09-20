"""Opt-in final numeric shop result confirmation; preserves original grant rules."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA=''
SLOT=0x7900
HOOK=0x39200
PREIMAGE=bytes.fromhex('201f92ad8606c916d006a9948d880660a98f8d880660')


def patch(original, helper):
    if len(original)!=0x200000 or len(helper)!=256:raise ValueError('Wrong ROM/helper extent')
    if original[HOOK:HOOK+len(PREIMAGE)]!=PREIMAGE:raise ValueError('Changed consume-finish hook')
    image=bytearray(original);allowed=set(range(0xffdc,0xffe0))|set(range(HOOK,HOOK+3))
    for bank in range(1,9):
        at=bank*65536+SLOT
        if original[at:at+256]!=b'\xff'*256:raise ValueError('Occupied shop hold helper slot')
        image[at:at+256]=helper;allowed.update(range(at,at+256))
    image[HOOK:HOOK+3]=bytes.fromhex('200079')
    checksum(image)
    if any(i not in allowed for i,(a,b) in enumerate(zip(original,image)) if a!=b):
        raise ValueError('Unrelated change')
    return image


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    pinned=Path('build/sprite-copy-game-3252/native-cpu.sfc')
    if sha(rom)!=meta['rom_sha256'] or sha(rom)!=sha(pinned):raise ValueError('Requires exact pinned3252 parent')
    out.mkdir(parents=True)
    for name in ('native_runtime.lbl','native_boot.lbl'):shutil.copy2(parent/name,out/name)
    subprocess.run(['.deps/cc65/bin/ca65','-o',str(out/'shop-hold.o'),'snes/shop_qol_final_hold.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/shop_qol_final_hold.cfg','-Ln',str(out/'shop-hold.lbl'),
                    '-o',str(out/'shop-hold.bin'),str(out/'shop-hold.o')],check=True)
    image=patch(rom.read_bytes(),(out/'shop-hold.bin').read_bytes())
    (out/'native-cpu.sfc').write_bytes(image)
    sources=[Path(__file__),Path('snes/shop_qol_final_hold.asm'),Path('snes/shop_qol_final_hold.cfg'),
        Path('tools/build_inline_pitch_trial.py'),Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),
        rom,parent/'manifest.json',out/'shop-hold.bin']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_shop_final_hold=dict(
        parent=str(parent),parent_sha256=sha(rom),sources={str(p):sha(p) for p in sources},
        helper=SLOT,hook=HOOK,enabled_in_this_opt_in_build=True,release_ready=False,
        scope='Hold final original consumption result until consuming player releases and presses A/B. '
              'No stat/economy/equipment/audio/graphics changes. Runtime qualification pending.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
