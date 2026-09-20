"""Remove the added trampoline from both original row-search call sites."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent,out):
    rom = parent/'native-cpu.sfc'
    if out.exists() or sha(rom) != '744c5f723cd8bf3826b255a1f4aaba2b46d541ccf43f5496a30c7296aa2da11a':
        raise ValueError('Exact3873 and fresh output required')
    image = bytearray(rom.read_bytes())
    sites = [i for i in range(65536) if image[i:i+3] == bytes.fromhex('4c8073')]
    if sites != [0x77c9,0x839e] or image[0x7380:0x7383] != bytes.fromhex('4c0040'):
        raise ValueError('Changed scanner call sites')
    for at in sites:image[at:at+3] = bytes.fromhex('4c0040')
    checksum(image)
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    meta = json.loads((parent/'manifest.json').read_text())
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_consumer_prefix24_direct=dict(
        sites=sites,release_ready=False,sources={str(p):sha(p) for p in
        (Path(__file__),Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json')}))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
