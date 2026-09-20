"""Preserve the displaced publisher's incoming A/P as well as its return frame."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT='fb0e5943fe9303952ed0143845430da2355264d58becf8ac15b2048de87416f0'


def patch(image):
    block=image[0xd900:0xda00]
    end=block.index(bytes.fromhex('4c9381'))
    if (block[:3]!=bytes.fromhex('ad3f00') or block[end+3:]!=b'\xff'*(253-end)
            or image[0x810d:0x8110]!=bytes.fromhex('2000d9')):
        raise ValueError('Changed mapped pause helper')
    # All internal transfers in this guarded helper are relative branches.
    # Prefixing PHP/PHA and inserting PLA/PLP at the common branch destination
    # leaves their displacements unchanged. The two external calls stay fixed.
    code=bytes.fromhex('0848')+block[:end]+bytes.fromhex('68284c9381')
    result=bytearray(image)
    result[0xd900:0xda00]=code+b'\xff'*(256-len(code))
    checksum(result)
    return bytes(result)


def build(parent,out):
    rom=parent/'native-cpu.sfc';meta=json.loads((parent/'manifest.json').read_text())
    if out.exists() or sha(rom)!=PARENT or meta['rom_sha256']!=PARENT:
        raise ValueError('Fresh output and exact mapped-helper parent required')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(patch(rom.read_bytes()))
    paths=[Path(__file__),rom,parent/'manifest.json',Path('tools/build_inline_pitch_trial.py')]
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_paused_audio_preserved=dict(
        sources={str(p):sha(p) for p in paths},release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
