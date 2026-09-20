"""Keep bank/APU adapters from re-enabling NMI during owned deferred sound service."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='4578e026751366607e4827bbf79c4c2f7dff9dd96455f510d6f3f82f5c5db034':
        raise ValueError('Exact3682 and fresh output required')
    original=rom.read_bytes();image=bytearray(original);changes=[]
    helper=bytes.fromhex('ee0a1c22005fc1ce0a1c6b')
    def change(at,before,after):
        if len(before)!=len(after) or image[at:at+len(before)]!=before:raise ValueError(hex(at))
        image[at:at+len(after)]=after;changes.append(dict(offset=at,before=before.hex(),after=after.hex()))
    sites=[i for i in range(len(original)) if original.startswith(bytes.fromhex('22005fc1'),i)]
    expected=[(bank<<16)+0x788d for bank in range(1,9)]
    if sites!=expected:raise ValueError(f'Changed real-driver service sites: {sites}')
    for bank,site in zip(range(1,9),sites):
        change((bank<<16)+0x7a80,b'\xff'*len(helper),helper)
        change(site,bytes.fromhex('22005fc1'),bytes.fromhex('22807ac1'))
    checksum(image);out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    meta=json.loads((parent/'manifest.json').read_text())
    sources=[Path(__file__),Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_audio_phase_depth=dict(
        sources={str(p):sha(p) for p in sources},changes=changes,helper_hex=helper.hex(),
        release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
