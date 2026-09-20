"""Create the post-publication restart A/B from an already validated packet player."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_postpublish_keyon import patch


def build(fixture, parent, out):
    manifest = bound_report(fixture/'manifest.json')
    game = json.loads((parent/'manifest.json').read_text())
    if manifest['source_rom_sha256'] != game['rom_sha256'] or sha(parent/'native-cpu.sfc') != game['rom_sha256']:
        raise ValueError('Different parent engine')
    original = (fixture/'engine.bin').read_bytes()
    if hashlib.sha256(original).hexdigest() != game['spc_sha256']:
        raise ValueError('Different player SPC')
    image = bytearray((fixture/'player.sfc').read_bytes())
    if image[0x120000:0x120000+len(original)] != original:
        raise ValueError('Player engine placement differs')
    engine, layout = patch(original, game['sweep_driver_layout'])
    image[0x120000:0x120000+len(engine)] = engine
    image[0xffdc:0xffe0] = b'\xff\xff\0\0'
    checksum = sum(image) & 65535
    struct.pack_into('<HH', image, 0xffdc, checksum ^ 65535, checksum)
    shutil.copytree(fixture, out)
    (out/'player.sfc').write_bytes(image)
    (out/'engine.bin').write_bytes(engine)
    manifest.update(rom_sha256=sha(out/'player.sfc'), spc_sha256=sha(out/'engine.bin'),
        mutation='postpublication-keyon-prototype', postpublish_keyon=layout,
        scope='Identical packet stream, upload length and player CPU code. Only checked SPC '
              'restart ordering and cartridge checksum differ from parent player.')
    # Retain all parent sources, and bind the new outputs separately.
    manifest['sources'].update({str(p): sha(p) for p in (Path(__file__),
        Path('tools/build_postpublish_keyon.py'), fixture/'manifest.json',
        parent/'manifest.json', parent/'native-cpu.sfc', out/'engine.bin', out/'player.sfc', out/'stream.bin')})
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=manifest['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('fixture', 'parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
