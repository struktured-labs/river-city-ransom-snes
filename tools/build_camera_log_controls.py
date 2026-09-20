"""Separate SRAM mapping and camera logger call/gate overhead from record writes."""
import argparse
import json
from pathlib import Path
import shutil

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent,out,mode):
    if out.exists() or mode not in ('mapping','gate'):
        raise ValueError('Fresh control and explicit mode required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:
        raise ValueError('Changed diagnostic')
    info=meta['diagnostic_camera_log']
    for path,digest in info['sources'].items():
        if sha(Path(path))!=digest:raise ValueError('Changed source: '+path)
    image=bytearray(rom.read_bytes());code=(parent/'logger.bin').read_bytes()
    if image[0xe000:0xe000+len(code)]!=code:
        raise ValueError('Changed logger code')
    if mode=='mapping':
        site=info['call_site']
        if image[site:site+3]!=bytes.fromhex('2000e0'):raise ValueError('Changed entry')
        image[site:site+3]=b'\x20'+labels(parent/'native_boot.lbl')['spc_frame'].to_bytes(2,'little')
    else:
        prefix=bytes.fromhex('af0e602048abc220af0c6020aa')
        skip=bytes.fromhex('e220684c')
        if code.count(prefix)!=1 or code.count(skip)!=1:
            raise ValueError('Ambiguous record/skip preimage')
        site=0xe000+code.index(prefix);target=0xe000+code.index(skip)+2
        image[site:site+3]=b'\x4c'+target.to_bytes(2,'little')
    checksum(image)
    out.mkdir(parents=True)
    (out/'native-cpu.sfc').write_bytes(image)
    for name in ('seed.srm','native_boot.lbl','native_runtime.lbl','logger.lbl'):
        shutil.copyfile(parent/name,out/name)
    (out/'logger.bin').write_bytes(image[0xe000:0xe000+len(code)])
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),camera_log_control=dict(mode=mode,
        changed_site=site,sources={str(p):sha(p) for p in (Path(__file__),rom,parent/'manifest.json',
            parent/'logger.bin',parent/'native_boot.lbl',Path('tools/build_inline_pitch_trial.py'))}))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),mode=mode,rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--mode',choices=('mapping','gate'),required=True)
    build(**vars(p.parse_args()))
