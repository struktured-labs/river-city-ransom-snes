"""Default-off prototype: restart pulse voices after live pitch/volume publication.

Patches only verified SPC instructions and unused upload padding. Engine length,
game CPU code, assets, sample directory and BRR samples stay unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

from tools.benchmark_report import sha
from tools.prepare_audio import _fast_reset_handler


def patch(engine, layout):
    data = bytearray(engine)
    changes = []

    def replace(at, old, new):
        if data[at:at+len(old)] != old or len(old) != len(new):
            raise ValueError(f'Post-publish KON preimage changed at {at:04x}')
        data[at:at+len(old)] = new
        changes.append(dict(offset=at, before=old.hex(), after=new.hex()))

    handler, labels = _fast_reset_handler()
    base = 0x2c1f
    if engine[base:base+len(handler)] != handler:
        raise ValueError('Need exact fast reset handler')
    # Keep the initial merged reset/duty mask in $54, but do not start voices
    # until SRCN, pitch and volume are ready. Same-size/same-cycle self-copy.
    replace(base+labels['keyon'], bytes.fromhex('8f4cf2fa54f3'), bytes.fromhex('8f4cf2fa5454'))
    for voice, name in enumerate(('duty0', 'duty1')):
        old = bytes.fromhex(f'e454d0068f4cf28f{1<<voice:02x}f36f')
        # Duty-only events join the mask too; preserve the caller's RET.
        new = bytes((0x18, 1 << voice, 0x54, 0x6f)) + bytes(len(old)-4)
        replace(base+labels[name], old, new)
    # The triangle attack/release helper uses $2B40..$2B74. This verified-zero
    # block follows it and precedes the original end of upload at $2C00.
    offset = 0x2b80
    helper = bytes.fromhex('e454f0068f4cf2c4f3008f00548f7df46f')
    # BEQ +6 skips the six-byte select/write sequence plus padding NOP.
    replace(offset, bytes(len(helper)), helper)
    ready = layout['driver']['ready'] - 0x400
    block = engine[ready:]
    old = bytes.fromhex('8f7df4')
    if block.count(old) != 1:
        raise ValueError('Ready acknowledgement is not unique')
    target = offset + 0x400
    replace(ready+block.index(old), old, bytes((0x3f, target & 255, target >> 8)))
    return bytes(data), dict(changes=changes, flush_entry=target,
        keyon_write_pc=target+9, ready_write_pc=target+16,
        engine_bytes=len(data), default_enabled=False)


def build(candidate, out):
    manifest = json.loads((candidate/'manifest.json').read_text())
    rom_path = candidate/'native-cpu.sfc'
    if not manifest.get('experimental_sweep_driver') or manifest['rom_sha256'] != sha(rom_path):
        raise ValueError('Need bound current live-sweep candidate')
    image = bytearray(rom_path.read_bytes())
    at = manifest['sweep_driver_rom_offset']
    size = manifest['sweep_driver_layout']['engine_bytes']
    original = bytes(image[at:at+size])
    if hashlib.sha256(original).hexdigest() != manifest['spc_sha256']:
        raise ValueError('Embedded engine identity mismatch')
    engine, layout = patch(original, manifest['sweep_driver_layout'])
    image[at:at+size] = engine
    image[0xffdc:0xffe0] = b'\xff\xff\0\0'
    checksum = sum(image) & 65535
    struct.pack_into('<HH', image, 0xffdc, checksum ^ 65535, checksum)
    shutil.copytree(candidate, out)
    (out/'native-cpu.sfc').write_bytes(image)
    manifest.update(rom_sha256=sha(out/'native-cpu.sfc'),
        spc_sha256=hashlib.sha256(engine).hexdigest(), experimental_postpublish_keyon=True,
        postpublish_keyon=dict(**layout, parent_rom_sha256=sha(rom_path),
            sources={str(p): sha(p) for p in (Path(__file__), Path('tools/prepare_audio.py'),
                candidate/'manifest.json', rom_path)}))
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=manifest['rom_sha256'], layout=layout), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    build(**vars(parser.parse_args()))
