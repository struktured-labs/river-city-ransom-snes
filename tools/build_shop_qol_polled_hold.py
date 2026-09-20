"""Build shop final-result hold with explicit original-game controller polling."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_shop_qol_final_hold import patch,SLOT,HOOK


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    pinned=Path('build/sprite-copy-game-3252/native-cpu.sfc')
    if sha(rom)!=meta['rom_sha256'] or sha(rom)!=sha(pinned):raise ValueError('Requires exact pinned3252')
    out.mkdir(parents=True)
    for name in ('native_runtime.lbl','native_boot.lbl'):shutil.copy2(parent/name,out/name)
    subprocess.run(['.deps/cc65/bin/ca65','-o',str(out/'shop-hold.o'),'snes/shop_qol_final_hold_polled.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/shop_qol_final_hold.cfg','-Ln',str(out/'shop-hold.lbl'),
                    '-o',str(out/'shop-hold.bin'),str(out/'shop-hold.o')],check=True)
    (out/'native-cpu.sfc').write_bytes(patch(rom.read_bytes(),(out/'shop-hold.bin').read_bytes()))
    sources=[Path(__file__),Path('snes/shop_qol_final_hold_polled.asm'),Path('snes/shop_qol_final_hold.cfg'),
        Path('tools/build_shop_qol_final_hold.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json',out/'shop-hold.bin']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_shop_final_hold=dict(
        parent=str(parent),parent_sha256=sha(rom),sources={str(p):sha(p) for p in sources},
        helper=SLOT,hook=HOOK,enabled_in_this_opt_in_build=True,release_ready=False,
        scope='v2 explicitly polls original pads while yielding, holds final result until '
              'consuming player releases and presses A/B. No stat/economy/equipment/audio/graphics changes.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
