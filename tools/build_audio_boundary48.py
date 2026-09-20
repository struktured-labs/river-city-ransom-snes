"""Trial: claim an already-pending sound tick before camera work from line48."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='aaa09580b6aaa8201e022089ccf91e3d51d35d32f15869961a1c73fec9ecec88':
        raise ValueError('Exact3819 and fresh output required')
    image=bytearray(rom.read_bytes());sites=[]
    for bank in range(1,9):
        at=bank*65536+0x7bb4
        if image[at:at+4]!=bytes.fromhex('e03c9007'):raise ValueError('Changed camera eligibility check')
        image[at+1]=48;sites.append(at+1)
    checksum(image);out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    meta=json.loads((parent/'manifest.json').read_text())
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_audio_boundary48=dict(
        sites=sites,old=60,new=48,release_ready=False,sources={str(p):sha(p) for p in
        (Path(__file__),Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json')}))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
