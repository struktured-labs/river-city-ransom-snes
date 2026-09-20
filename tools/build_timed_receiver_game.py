"""Integrate settled staged SPC receiver and per-packet beam-relative deadline."""
import argparse
import json
from pathlib import Path
import shutil
import time
from tools.benchmark_report import sha
from tools.review_command_priority import bound
from tools.build_restart_volume_game import embed
from tools.build_inline_pitch_trial import checksum


def helper(target):
    if target==0:return bytes.fromhex('9c4321a0000060')
    if target!=200:raise ValueError('Only immediate control or line200 experiment')
    b=bytearray();labels={};fix=[]
    def put(s):b.extend(bytes.fromhex(s))
    def branch(op,label):b.extend((op,0));fix.append((len(b)-1,label))
    # Read both latched V-counter bytes. No shared WRAM scratch or busy wait.
    put('ad3f21ad3721ad3d2148ad3d212901');branch(0xd0,'high')
    put('68c9c8');branch(0xb0,'late')
    # floor((200-line)/8). Approximate SPC512-clock ticks; late packets
    # commit immediately. Recomputed every packet: no free-running drift.
    put('49ff1869c94a4a4a8d4321a0000060')
    labels['high']=len(b);put('68');labels['late']=len(b)
    put('a9008d4321a0000060')
    for at,label in fix:
        delta=labels[label]-at-1
        if not -128<=delta<=127:raise ValueError('Branch extent')
        b[at]=delta&255
    return bytes(b)


def build(parent,fixture,target,out):
    start=time.monotonic()
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!='f6f69215716ecc077c9082da0a20db1eaaa064daab81b0992a54cade834d1e16':raise ValueError('Exact3955 parent required')
    proof=bound(fixture/'manifest.json');engine=(fixture/'engine.bin').read_bytes()
    if sha(fixture/'engine.bin')!=proof['engine_sha256']:raise ValueError('Changed engine')
    image,changes=embed(rom.read_bytes(),engine,meta['sweep_driver_rom_offset'],meta['sweep_driver_layout']['engine_bytes'],0xd290)
    b=bytearray(image);code=helper(target)
    if b[0xd2cd:0xd2d0]!=bytes.fromhex('a00000') or b[0xf000:0xf000+len(code)]!=b'\xff'*len(code):
        raise ValueError('Changed sender or occupied helper')
    b[0xd2cd:0xd2d0]=bytes.fromhex('2000f0');b[0xf000:0xf000+len(code)]=code;checksum(b)
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(b);(out/'engine.bin').write_bytes(engine)
    paths=[Path(__file__),Path('tools/build_restart_volume_game.py'),Path('tools/build_inline_pitch_trial.py'),
        rom,parent/'manifest.json',fixture/'manifest.json',fixture/'engine.bin']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),spc_sha256=sha(out/'engine.bin'),
        sweep_driver_layout=dict(meta['sweep_driver_layout'],engine_bytes=len(engine)),
        experimental_timed_receiver=dict(target_line=target,helper=code.hex(),upload=changes,spc_labels=proof['labels'],
            sources={str(p):sha(p) for p in paths},release_ready=False,scope=__doc__+
            ' Coarse beam conversion, no CPU wait. Not exact display/SPC clock synchronization.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=meta['rom_sha256'],target=target,seconds=time.monotonic()-start)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','fixture','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--target',type=int,choices=(0,200),required=True)
    build(**vars(p.parse_args()))
