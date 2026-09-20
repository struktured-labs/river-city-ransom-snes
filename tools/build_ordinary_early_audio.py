"""Trial: service ordinary visible-game audio before the original interrupt body."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def patch(image, helper, dispatch):
    if len(image) != 0x200000 or len(helper) != 512:
        raise ValueError('Wrong cartridge/helper extent')
    if image[dispatch:dispatch+4] != bytes.fromhex('68dc001c'):
        raise ValueError('Changed native game dispatch')
    result = bytearray(image)
    allowed = set(range(dispatch,dispatch+4)) | set(range(0xffdc,0xffe0))
    result[dispatch:dispatch+4] = bytes.fromhex('5c0076c1')
    for bank in range(1,9):
        first = bank*65536+0x7600
        if image[first:first+512] != b'\xff'*512:
            raise ValueError('Occupied ordinary-audio helper slot')
        result[first:first+512] = helper
        allowed.update(range(first,first+512))
    checksum(result)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a != b):
        raise ValueError('Unrelated cartridge mutation')
    return result


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh candidate required')
    meta = json.loads((parent/'manifest.json').read_text())
    if sha(parent/'native-cpu.sfc') != meta['rom_sha256'] or not meta.get('experimental_final_batch_slack'):
        raise ValueError('Need authenticated final-batch parent')
    boot = symbols(parent/'native_boot.lbl')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():
            shutil.copy2(p,out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65','-o',str(out/'ordinary-audio.o'),
                    'snes/ordinary_early_audio.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/ordinary_early_audio.cfg',
        '-Ln',str(out/'ordinary-audio.lbl'),'-o',str(out/'ordinary-audio.bin'),
        str(out/'ordinary-audio.o')],check=True)
    rom = parent/'native-cpu.sfc'; helper = out/'ordinary-audio.bin'
    image = patch(rom.read_bytes(),helper.read_bytes(),boot['@game_nmi'])
    (out/'native-cpu.sfc').write_bytes(image)
    files = [Path(__file__),Path('snes/ordinary_early_audio.asm'),Path('snes/ordinary_early_audio.cfg'),
        Path('tools/build_inline_pitch_trial.py'),Path('tools/build_retained_producer_guard.py'),
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json',
        parent/'native_boot.lbl',helper,out/'ordinary-audio.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_ordinary_early_audio=dict(
        parent=str(parent),dispatch=boot['@game_nmi'],helper=0x7600,size=512,
        sources={str(p):sha(p) for p in files},release_ready=False,
        scope=__doc__+' Existing early-audio helper and exact native-ID suppression reused. '
        'Busy/menu/transition paths remain at their original audio sites. '
        'Original interrupt-body ordering changes for eligible visible gameplay; qualification required.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):parser.add_argument('--'+k,type=Path,required=True)
    build(**vars(parser.parse_args()))
