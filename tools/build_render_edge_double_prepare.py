"""Default-off two-pass edge experiment; existing row limits remain in force."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_render_edge_prepare import patch,HELPER


def build(parent,out):
    if out.exists():raise ValueError('Fresh candidate required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed parent')
    symbols={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (parent/'native_boot.lbl').read_text().splitlines()}
    bridge=symbols['video_prepare_bridge']
    shutil.copytree(parent,out)
    subprocess.run(['.deps/cc65/bin/ca65','-D',f'PREPARE_BRIDGE={bridge}',
        '-o',str(out/'edge.o'),'snes/render_edge_prepare_double.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/render_edge_prepare.cfg',
        '-o',str(out/'edge.bin'),str(out/'edge.o')],check=True)
    data,sites=patch(rom.read_bytes(),(out/'edge.bin').read_bytes())
    (out/'native-cpu.sfc').write_bytes(data)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_render_edge_prepare=dict(
        helper=HELPER,sites=sites,bridge=bridge,passes=2,default_enabled=False,release_ready=False,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/build_render_edge_prepare.py'),
            Path('snes/render_edge_prepare_double.asm'),Path('snes/render_edge_prepare.cfg'),
            Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json',
            parent/'native_boot.lbl',out/'edge.bin')}))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
