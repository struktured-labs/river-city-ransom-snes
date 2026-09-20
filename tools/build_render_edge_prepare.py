"""Default-off one bounded hidden preparation at a genuine render-on edge."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

HELPER=0x7f80
PATTERN=bytes.fromhex('a9018d851ca9028da01cad0a1c')


def assemble(out,bridge):
    if not 0x8000<=bridge<0xffc0:raise ValueError('Invalid native bridge address')
    subprocess.run(['.deps/cc65/bin/ca65','-D',f'PREPARE_BRIDGE={bridge}',
        '-o',str(out/'edge.o'),'snes/render_edge_prepare.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/render_edge_prepare.cfg',
        '-o',str(out/'edge.bin'),str(out/'edge.o')],check=True)
    return (out/'edge.bin').read_bytes()


def patch(image,helper):
    if len(helper)!=64 or helper[:5]!=bytes.fromhex('8da01c0848'):
        raise ValueError('Unexpected edge helper')
    result=bytearray(image);allowed=set(range(0xffdc,0xffe0));sites=[]
    for bank in range(1,9):
        base=bank*65536;block=image[base:base+65536]
        if block.count(PATTERN)!=1 or block[HELPER:HELPER+64]!=b'\xff'*64:
            raise ValueError('Missing/ambiguous edge or occupied helper')
        site=block.index(PATTERN)+7
        if not 0x2000<site<0x4000 or block[site:site+3]!=bytes.fromhex('8da01c'):
            raise ValueError('Unexpected render-on store')
        result[base+site:base+site+3]=b'\x20'+HELPER.to_bytes(2,'little')
        result[base+HELPER:base+HELPER+64]=helper
        allowed.update(range(base+site,base+site+3));allowed.update(range(base+HELPER,base+HELPER+64))
        sites.append(dict(bank=bank,site=site))
    checksum(result)
    if len(result)!=len(image) or any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b):
        raise ValueError('Unrelated cartridge mutation')
    return bytes(result),sites


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed parent')
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (parent/'native_boot.lbl').read_text().splitlines()}
    shutil.copytree(parent,out)
    helper=assemble(out,labels['video_prepare_bridge']);data,sites=patch(rom.read_bytes(),helper)
    (out/'native-cpu.sfc').write_bytes(data)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_render_edge_prepare=dict(
        helper=HELPER,sites=sites,bridge=labels['video_prepare_bridge'],default_enabled=False,release_ready=False,
        sources={str(p):sha(p) for p in (Path(__file__),Path('snes/render_edge_prepare.asm'),
            Path('snes/render_edge_prepare.cfg'),Path('tools/build_inline_pitch_trial.py'),
            rom,parent/'manifest.json',parent/'native_boot.lbl',out/'edge.bin')}))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),sha256=meta['rom_sha256'],sites=sites)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
