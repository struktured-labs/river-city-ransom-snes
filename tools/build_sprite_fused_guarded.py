"""Use fused sprite copy only in gameplay; keep original fallback copy instructions."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_sprite_fused_copy import patch


def source():
    text = Path('snes/sprite_fused_copy.asm').read_text()
    marker = '    lda a:$1C79\n'
    if text.count(marker) != 1 or text.count('        sta a:$1000 + word*2') != 1:
        raise ValueError('Changed fused template')
    # Outside the original active-game task, retain the prior full converter.
    text = text.replace(marker, '''    lda a:$0100
    and #$C0
    cmp #$C0
    beq :+
    jmp fallback
:
'''+marker)
    return text.replace('        sta a:$1000 + word*2', '        sta f:$7E1000 + word*2')


def build(parent, out):
    if out.exists(): raise ValueError('Fresh candidate required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256'] or not meta.get('experimental_sprite_copy_prepare'):
        raise ValueError('Need bound sprite3252 parent')
    boot=labels(parent/'native_boot.lbl');runtime=labels(parent/'native_runtime.lbl')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    asm=out/'sprite-fused-guarded.asm';asm.write_text(source())
    defs=dict(SPRITE_Y_MAP=boot['sprite_y_map'],SPRITE_ATTR_MAP=boot['sprite_attribute_map'])
    subprocess.run(['.deps/cc65/bin/ca65',*[s for k,v in defs.items() for s in ('-D',f'{k}={v}')],
        '-o',str(out/'sprite-fused.o'),str(asm)],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/sprite_fused_copy.cfg','-Ln',str(out/'sprite-fused.lbl'),
        '-o',str(out/'sprite-fused.bin'),str(out/'sprite-fused.o')],check=True)
    image,sites=patch(rom.read_bytes(),(out/'sprite-fused.bin').read_bytes(),runtime['@dma_copied'],
        (parent/'sprite-copy.bin').read_bytes())
    (out/'native-cpu.sfc').write_bytes(image)
    files=[Path(__file__),Path('tools/build_sprite_fused_copy.py'),Path('snes/sprite_fused_copy.asm'),
        Path('snes/sprite_fused_copy.cfg'),Path('tools/audio_packet_log.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json',
        parent/'native_boot.lbl',parent/'native_runtime.lbl',parent/'sprite-copy.bin',asm,
        out/'sprite-fused.bin',out/'sprite-fused.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_sprite_fused_copy=dict(
        parent=str(parent),sites=sites,sources={str(p):sha(p) for p in files},release_ready=False,
        scope=__doc__+' Fast conversion applies only to initialized page02, matching pattern half, '
        'no transition and task C0; no content change. Source event remains full-shadow-copy completion.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
