"""Place the pause helper in bank-00-visible ROM: the NMI publisher JSR has PB=00."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tools import build_paused_prepublication_audio as base
from tools.benchmark_report import sha


def build(parent, out):
    rom=parent/'native-cpu.sfc'
    meta=json.loads((parent/'manifest.json').read_text())
    if out.exists() or sha(rom)!=base.PARENT_SHA or meta['rom_sha256']!=base.PARENT_SHA:
        raise ValueError('Need fresh output and exact mixed-scan parent')
    paths=[Path(__file__),Path(base.__file__),Path('snes/paused_prepublication_audio.asm'),
        Path('snes/paused_audio_bank_fix.cfg'),Path('tools/build_inline_pitch_trial.py'),
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json']
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65','-o',str(out/'paused-bank.o'),
        'snes/paused_prepublication_audio.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/paused_audio_bank_fix.cfg',
        '-Ln',str(out/'paused-bank.lbl'),'-o',str(out/'paused-bank.bin'),
        str(out/'paused-bank.o')],check=True)
    previous=base.SLOT
    try:
        base.SLOT=0xd900
        result,site=base.patch(rom.read_bytes(),(out/'paused-bank.bin').read_bytes())
    finally:base.SLOT=previous
    (out/'native-cpu.sfc').write_bytes(result)
    paths.extend((out/'paused-bank.bin',out/'paused-bank.lbl'))
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_paused_prepublication_audio=dict(
        sources={str(p):sha(p) for p in paths},site=site,helper=0xd900,release_ready=False,
        scope=__doc__+' Same pause-only timing experiment, corrected mapped continuation. '
        'Failed7500 candidate retained. Graphics timing unqualified.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
