"""Offline camera-recorder coverage trial: admit through line229, not line193."""
import argparse
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def replace_cutoff(code):
    signature=bytes.fromhex('8ac9c2b0')
    if code.count(signature)!=1:
        raise ValueError('Need unique TXA/CMP194/BCS admission guard')
    return code.replace(signature,bytes.fromhex('8ac9e6b0'))


def patch(image, wait, idle):
    if len(image)!=0x200000:
        raise ValueError('Need exact HiROM extent')
    result=bytearray(image)
    allowed=set(range(0xffdc,0xffe0))
    for code,address,banks in ((wait,0x7b00,range(1,9)),(idle,0xe400,[0])):
        changed=replace_cutoff(code)
        for bank in banks:
            start=bank*65536+address
            if image[start:start+len(code)]!=code:
                raise ValueError('Actual cartridge guard differs')
            result[start:start+len(code)]=changed
            allowed.add(start+code.index(bytes.fromhex('8ac9c2b0'))+2)
    checksum(result)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b):
        raise ValueError('Unrelated change')
    return bytes(result)


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text())
    rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256'] or meta['experimental_raster']:
        raise ValueError('Need authenticated non-raster parent')
    wait,idle=((parent/(name+'.bin')).read_bytes() for name in ('wait','idle'))
    result=patch(rom.read_bytes(),wait,idle)
    shutil.copytree(parent,out)
    (out/'native-cpu.sfc').write_bytes(result)
    (out/'wait.bin').write_bytes(replace_cutoff(wait))
    (out/'idle.bin').write_bytes(replace_cutoff(idle))
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),late_camera_log=dict(
        cutoff=230,qualified=False,deployed=False,
        scope='Only nine admission operands and cartridge checksum change. '
              'Must requalify interrupt deadline and camera behavior before physical use.',
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/build_inline_pitch_trial.py'),
            rom,parent/'manifest.json',parent/'wait.bin',parent/'idle.bin')}))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
