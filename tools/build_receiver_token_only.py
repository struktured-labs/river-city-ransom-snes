"""Ablate command publication priority from4007; retain only data-token priority over3955."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

def patch(engine):
    if hashlib.sha256(engine).hexdigest()!='6477cff285c233a89a128675dd1cec7c3499bd1316922a2ec635260ecc9bfbf7':raise ValueError('Exact4007 engine required')
    b=bytearray(engine)
    if b[0x3055:0x3058]!=bytes.fromhex('5f2335') or b[0x3123:0x3130]!=bytes.fromhex('3f7232e4f468d7f0035f58346f'):raise ValueError('Changed command helper')
    b[0x3055:0x3058]=bytes.fromhex('3f7232');b[0x3123:0x3130]=bytes(13)
    return bytes(b)

def build(parent,out):
    rom=parent/'native-cpu.sfc'
    if out.exists() or sha(rom)!='839b76b4767a6e74dee1166d1c3bbf9e8298fb64bc00f8007033524a434cd0cc':raise ValueError('Exact4007 and fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());old=rom.read_bytes();b=bytearray(old)
    at=meta['sweep_driver_rom_offset'];size=meta['sweep_driver_layout']['engine_bytes']
    engine=patch(bytes(b[at:at+size]));b[at:at+size]=engine;checksum(b)
    allowed=set(range(at+0x3055,at+0x3058))|set(range(at+0x3123,at+0x3130))|set(range(0xffdc,0xffe0))
    if len(b)!=len(old) or any(i not in allowed for i,(x,y) in enumerate(zip(old,b)) if x!=y):raise ValueError('Unrelated mutation')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(b)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),spc_sha256=hashlib.sha256(engine).hexdigest(),
        command_priority_reverted=True,experimental_receiver_token_only=dict(release_ready=False,
            sources={str(p):sha(p) for p in (Path(__file__),Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json')},scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=meta['rom_sha256'],spc_sha256=meta['spc_sha256'])))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
