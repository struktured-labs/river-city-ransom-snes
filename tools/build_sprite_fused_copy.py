"""Fuse page-copy and sprite conversion without changing original sprite content."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

SLOT, SIZE = 0x2000, 0x1800
# Fast C=0 only restores the displaced accumulator effect. C=1 (including
# unchanged MVN fallback) tail-calls the original3252 helper relocated to7900.
POST = bytes.fromhex('b007e220a901c2206b5c0079c0')


def copy_pattern():
    return b''.join(bytes((0xa5, i, 0x8f, i, 0x10, 0x7e)) for i in range(0, 256, 2))


def patch(original, helper, site, old_post):
    if len(original) != 0x200000 or len(helper) != SIZE or len(old_post) != 256:
        raise ValueError('Wrong extent')
    if original[SLOT:SLOT+SIZE] != b'\xff'*SIZE or original[0x7900:0x7a00] != b'\xff'*256:
        raise ValueError('Occupied helper extent')
    if original[0x7800:0x7900] != old_post: raise ValueError('Changed post-copy helper')
    image = bytearray(original); allowed = set(range(SLOT, SLOT+SIZE))
    allowed.update(range(0x7800, 0x7a00)); allowed.update(range(0xffdc, 0xffe0))
    image[SLOT:SLOT+SIZE] = helper
    image[0x7900:0x7a00] = old_post
    image[0x7800:0x7900] = POST+b'\xff'*(256-len(POST))
    sites = []
    for bank in range(1, 9):
        base = bank*65536; chunk = original[base:base+65536]; pattern = copy_pattern()
        if chunk.count(pattern) != 1: raise ValueError('Missing unique original unrolled copy')
        start = chunk.index(pattern)
        if chunk[start-2:start] != bytes.fromhex('eb5b'):
            raise ValueError('Source direct page not established by original XBA/TCD')
        if chunk[site:site+9] != bytes.fromhex('220078c0eaeaeaeaea'):
            raise ValueError('Different source-event/post-copy hook')
        image[base+start:base+start+7] = bytes.fromhex('220020c04c')+site.to_bytes(2,'little')
        allowed.update(range(base+start, base+start+7)); sites.append(base+start)
    checksum(image)
    if any(i not in allowed for i, (a,b) in enumerate(zip(original,image)) if a != b):
        raise ValueError('Unrelated mutation')
    return image, sites


def build(parent, out):
    if out.exists(): raise ValueError('Fresh candidate required')
    rom = parent/'native-cpu.sfc'; meta = json.loads((parent/'manifest.json').read_text())
    if sha(rom) != meta['rom_sha256'] or not meta.get('experimental_sprite_copy_prepare'):
        raise ValueError('Need bound3252 sprite-copy parent')
    boot = labels(parent/'native_boot.lbl'); runtime = labels(parent/'native_runtime.lbl')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file(): shutil.copy2(p, out/p.name)
    defs = dict(SPRITE_Y_MAP=boot['sprite_y_map'], SPRITE_ATTR_MAP=boot['sprite_attribute_map'])
    subprocess.run(['.deps/cc65/bin/ca65', *[s for k,v in defs.items() for s in ('-D',f'{k}={v}')],
        '-o',str(out/'sprite-fused.o'),'snes/sprite_fused_copy.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/sprite_fused_copy.cfg','-Ln',str(out/'sprite-fused.lbl'),
        '-o',str(out/'sprite-fused.bin'),str(out/'sprite-fused.o')], check=True)
    image, sites = patch(rom.read_bytes(), (out/'sprite-fused.bin').read_bytes(), runtime['@dma_copied'],
                         (parent/'sprite-copy.bin').read_bytes())
    (out/'native-cpu.sfc').write_bytes(image)
    files = [Path(__file__),Path('snes/sprite_fused_copy.asm'),Path('snes/sprite_fused_copy.cfg'),
        Path('tests/test_sprite_fused_copy.py'),Path('tools/audio_packet_log.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),rom,parent/'manifest.json',
        parent/'native_runtime.lbl',parent/'native_boot.lbl',parent/'sprite-copy.bin',
        out/'sprite-fused.bin',out/'sprite-fused.lbl']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_sprite_fused_copy=dict(
        parent=str(parent), sites=sites, sources={str(p):sha(p) for p in files}, release_ready=False,
        scope=__doc__+' The source event remains at the complete-shadow-copy boundary; '
        'conversion now occurs during that copy. Fast path requires initialized matching pattern half '
        'and no hidden transition; other cases retain original3252 conversion. SPC unchanged.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],sites=sites)))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
