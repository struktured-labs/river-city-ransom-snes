"""Retain the interrupted game data bank when entering the real sound driver."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='1899551c2df4dfa2fd72a89517fb4ded95184e7b840754de40dd1c4632d8a17a':
        raise ValueError('Exact3663 and fresh output required')
    meta=json.loads((parent/'manifest.json').read_text())
    image=bytearray(rom.read_bytes())
    prefix=bytes.fromhex('0848da5a0b8bd8f400002ba90048ab')
    changes=[]
    for bank in range(1,9):
        first=(bank<<16)+0x7800
        hits=[i for i in range(first,first+768) if image.startswith(prefix,i)]
        if len(hits)!=4:raise ValueError('Changed context wrappers')
        for i in hits:
            offset=i+11
            image[offset:offset+4]=b'\xea'*4
            changes.append(dict(offset=offset,before='a90048ab',after='eaeaeaea'))
    checksum(image)
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    sources=[Path(__file__),Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_audio_phase_bank=dict(
        sources={str(p):sha(p) for p in sources},changes=changes,release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
