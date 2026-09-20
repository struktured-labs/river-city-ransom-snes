"""Restore baseline early service while retaining the new pre-retained recovery."""
import argparse
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def patch(data):
    image=bytearray(data)
    for bank in range(1,9):
        at=bank*65536+0x7be0
        if image[at:at+8]!=bytes.fromhex('9c00424c5f32a31c'):
            raise ValueError('Changed ablation entry')
        image[at+3:at+6]=bytes.fromhex('0848ad')
    checksum(image)
    return image


def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='0781da9b83237d4e98c5d65aef0a886e1ce6e21d01ac91a1af4afe6d6234cec3':
        raise ValueError('Exact4041 and fresh output required')
    image=patch(rom.read_bytes());out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    meta=json.loads((parent/'manifest.json').read_text())
    paths=[Path(__file__),Path('tests/test_audio_dual_boundary.py'),Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_audio_dual_boundary=dict(
        sources={str(p):sha(p) for p in paths},camera_pre_service_restored=True,release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
