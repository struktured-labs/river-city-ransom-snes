"""Pause-only sound service before graphics publication; no new sound-driver tick."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA = 'f56ab5f1df86762993c584821461e3197a96913ddb1f54175f27d66d4db33515'
SLOT = 0x7500


def patch(image, helper):
    if len(image) != 0x200000 or len(helper) != 256:
        raise ValueError('Wrong cartridge/helper size')
    if image[SLOT:SLOT+256] != b'\xff'*256:
        raise ValueError('Occupied helper slot')
    needle = bytes.fromhex('209381')
    block = image[0x80fb:0x818f]
    if block.count(needle) != 1:
        raise ValueError('Missing or ambiguous native publisher call')
    site = 0x80fb + block.index(needle)
    if image[0x1818f:0x18193] == bytes.fromhex('5c0076c1'):
        raise ValueError('Unexpected replicated native boot')
    if image[0x818f:0x8193] != bytes.fromhex('5c0076c1'):
        raise ValueError('Ordinary early-audio dispatcher changed')
    if image[0x15f00:0x15f07] != bytes.fromhex('0848da5a0b8bf4'):
        raise ValueError('Early-audio register preservation changed')
    result = bytearray(image)
    result[site:site+3] = b'\x20'+SLOT.to_bytes(2, 'little')
    result[SLOT:SLOT+256] = helper
    checksum(result)
    allowed = set(range(site,site+3)) | set(range(SLOT,SLOT+256)) | set(range(0xffdc,0xffe0))
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a != b):
        raise ValueError('Unrelated cartridge edit')
    return bytes(result), site


def build(parent, out):
    rom = parent/'native-cpu.sfc'
    meta = json.loads((parent/'manifest.json').read_text())
    if out.exists() or sha(rom) != PARENT_SHA or meta['rom_sha256'] != PARENT_SHA:
        raise ValueError('Need fresh output and exact qualified mixed-scan parent')
    paths = [Path(__file__), Path('snes/paused_prepublication_audio.asm'),
        Path('snes/paused_prepublication_audio.cfg'), Path('tools/build_inline_pitch_trial.py'),
        Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65'), rom, parent/'manifest.json']
    sources = {str(p):sha(p) for p in paths}
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file(): shutil.copy2(p, out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65','-o',str(out/'paused-audio.o'),
        'snes/paused_prepublication_audio.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/paused_prepublication_audio.cfg',
        '-Ln',str(out/'paused-audio.lbl'),'-o',str(out/'paused-audio.bin'),
        str(out/'paused-audio.o')],check=True)
    result, site = patch(rom.read_bytes(),(out/'paused-audio.bin').read_bytes())
    (out/'native-cpu.sfc').write_bytes(result)
    sources.update({str(p):sha(p) for p in (out/'paused-audio.bin',out/'paused-audio.lbl')})
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_paused_prepublication_audio=dict(
        sources=sources, site=site, helper=SLOT, release_ready=False,
        scope=__doc__+' Exact native-ID suppression reused. Graphics time-budget tradeoff unqualified.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],site=site)))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
