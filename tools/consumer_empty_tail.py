"""Finish empty scalar queue entries locally; keep deadlines and row order intact."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.consumer_word_entry_fix import validate_entry

PARENTS={
    'f56ab5f1df86762993c584821461e3197a96913ddb1f54175f27d66d4db33515',
    '05b4856f5d8bd87ba0fd295ec5325fa1539f104b57e7e95018813bf76b4ccf45'}


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-empty-tail-') as temp:
        obj=Path(temp)/'helper.o';binary=Path(temp)/'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65','-o',str(obj),'snes/consumer_empty_tail.asm'],check=True)
        subprocess.run(['.deps/cc65/bin/ld65','-C','snes/consumer_linear_scan.cfg',
            '-o',str(binary),str(obj)],check=True)
        return binary.read_bytes()


def patch(image,helper):
    from tools.consumer_mixed_scan import assemble as old_assemble
    if hashlib.sha256(image).hexdigest() not in PARENTS:raise ValueError('Unqualified parent')
    validate_entry(image)
    old=old_assemble()
    if (image[0x839e:0x83a3]!=bytes.fromhex('4c8073eaea') or not len(old)<len(helper)<=0x480
            or image[0x7380:0x7380+len(old)]!=old
            or image[0x7380+len(old):0x7380+len(helper)]!=b'\xff'*(len(helper)-len(old))):
        raise ValueError('Changed queue helper or occupied extension')
    result=bytearray(image);result[0x7380:0x7380+len(helper)]=helper;checksum(result)
    if any(not(0x7380<=i<0x7380+len(helper) or 0xffdc<=i<0xffe0)
            for i,(a,b) in enumerate(zip(image,result)) if a!=b):
        raise ValueError('Unrelated cartridge mutation')
    return bytes(result)


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    rom=parent/'native-cpu.sfc';meta=json.loads((parent/'manifest.json').read_text())
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed parent')
    helper=assemble();image=patch(rom.read_bytes(),helper)
    paths=[Path(__file__),Path('snes/consumer_empty_tail.asm'),Path('snes/consumer_linear_scan.cfg'),
        Path('tools/consumer_mixed_scan.py'),Path('snes/consumer_mixed_scan.asm'),
        Path('tools/consumer_word_entry_fix.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json']
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    (out/'consumer-empty-tail.bin').write_bytes(helper)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_consumer_empty_tail=dict(
        sources={str(p):sha(p) for p in paths},helper_hex=helper.hex(),release_ready=False,
        scope=__doc__+' No audio, producer, game logic, DMA cutoff, or new state changes.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],helper_bytes=len(helper))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
