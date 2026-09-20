"""Offline game trial: restart-pitch staging in verified existing SPC padding."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_startup_pitch_trial import ENGINE_SHA

STAGE = (0x2f80, 0x2faa)
ORDINARY = (0x2f29, 0x2f33)
FINISH = 0x2f74
VALID = 0x2f95
FLUSH = 0x2fbf


def relative(origin, offset, target):
    delta = target-(origin+offset+2)
    if not -128 <= delta <= 127:
        raise ValueError('Startup branch out of range')
    return delta & 255


def sections():
    result = {}
    for voice in (0, 1):
        address = VALID+1+2*voice
        stage = bytes((0xe4, 0x54, 0x28, 1 << voice,
            0xf0, relative(STAGE[voice], 4, ORDINARY[voice]),
            0xc9, address & 255, address >> 8,
            0xcc, (address+1) & 255, (address+1) >> 8,
            0xe5, VALID & 255, VALID >> 8, 0x08, 1 << voice,
            0xc5, VALID & 255, VALID >> 8, 0x6f))
        ordinary = bytes((0xe8, voice*16+3, 0x8f, voice*16+2, 0xf2,
                          0xd8, 0xf3, 0xda, 0xf2, 0x6f))
        result[STAGE[voice]] = stage; result[ORDINARY[voice]] = ordinary
    flush = bytearray((0xe4, 0x54, 0xf0, relative(FLUSH, 2, FINISH),
                       0x8f, 0x4c, 0xf2, 0xc4, 0xf3, 0xcd, 16, 0x1d, 0xd0, 0xfd))
    for voice in (0, 1):
        address = VALID+1+2*voice
        body = bytes((0x8f, voice*16+2, 0xf2,
            0xe5, address & 255, address >> 8, 0xc4, 0xf3,
            0xe5, (address+1) & 255, (address+1) >> 8, 0xab, 0xf2, 0xc4, 0xf3))
        flush.extend((0xe5, VALID & 255, VALID >> 8, 0x28, 1 << voice, 0xf0, len(body)))
        flush.extend(body)
    flush.extend((0x5f, FINISH & 255, FINISH >> 8))
    result[FLUSH] = bytes(flush)
    result[FINISH] = bytes((0xe8, 0, 0xc5, VALID & 255, VALID >> 8,
                           0xc4, 0x54, 0x8f, 0x7d, 0xf4, 0x6f))
    result[VALID] = bytes(5)
    spans = sorted((at, at+len(code)) for at, code in result.items())
    if any(b > c for (a, b), (c, d) in zip(spans, spans[1:])):
        raise ValueError('Overlapping helper/storage sections')
    if any(a < 0x2faa and b > 0x2fa0 for a, b in spans):
        raise ValueError('Helper overwrites receiver poll code')
    if max(b for a, b in spans) > 0x3000:
        raise ValueError('Helper overlaps receiver/reset code')
    return result


def patch(engine, layout):
    if len(engine) != 12415 or hashlib.sha256(engine).hexdigest() != ENGINE_SHA:
        raise ValueError('Need exact current engine')
    data = bytearray(engine); changes = []
    for a, b in ((0x2b29, 0x2b40), (0x2b74, 0x2b80), (0x2b91, 0x2ba0), (0x2baa, 0x2c00)):
        if engine[a:b] != bytes(b-a):
            raise ValueError('Occupied helper padding')
    old = bytes.fromhex('e454f0068f4cf2c4f3008f00548f7df46f')
    if engine[0x2b80:0x2b91] != old:
        raise ValueError('Changed postpublication helper')
    if engine[0x2ba0:0x2baa] != bytes.fromhex('e4fdf0033f84325fda32'):
        raise ValueError('Changed retained receiver helper')
    for address, code in sections().items():
        at = address-0x400
        changes.append(dict(offset=at, before=bytes(data[at:at+len(code)]).hex(), after=code.hex()))
        data[at:at+len(code)] = code
    for voice in (0, 1):
        at = layout['driver'][f'publish{voice}_audible']-0x400+33
        old = bytes((0x8f, voice*16+2, 0xf2, 0xd8, 0xf3, 0xda, 0xf2))
        new = bytes((0x3f, STAGE[voice] & 255, STAGE[voice] >> 8))+bytes(4)
        if data[at:at+7] != old:
            raise ValueError('Changed word-pitch publisher')
        data[at:at+7] = new
        changes.append(dict(offset=at, before=old.hex(), after=new.hex()))
    # Only the known last call of the ready path is redirected. Do not search
    # for a globally unique ready token: the legacy engine has several.
    at = layout['engine_bytes']-4
    if engine[at:at+4] != bytes.fromhex('3f802f6f'):
        raise ValueError('Changed ready flush call')
    new = bytes((0x3f, FLUSH & 255, FLUSH >> 8))
    data[at:at+3] = new
    changes.append(dict(offset=at, before='3f802f', after=new.hex()))
    if data[0x2ba0:0x2baa] != engine[0x2ba0:0x2baa]:
        raise ValueError('Receiver helper changed')
    return bytes(data), dict(changes=changes, stage=list(STAGE), ordinary=list(ORDINARY),
        finish=FINISH, flush=FLUSH, storage=VALID, engine_bytes=len(engine),
        upload_length_unchanged=True, default_enabled=False, scope=__doc__)


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh game candidate required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'; image = bytearray(rom.read_bytes())
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Unbound parent cartridge')
    at = meta['sweep_driver_rom_offset']; size = meta['sweep_driver_layout']['engine_bytes']
    engine, detail = patch(bytes(image[at:at+size]), meta['sweep_driver_layout'])
    image[at:at+size] = engine
    checksum(image)
    allowed = {at+c['offset']+i for c in detail['changes'] for i in range(len(bytes.fromhex(c['after'])))}
    allowed.update(range(0xffdc, 0xffe0))
    if any(i not in allowed for i, (a, b) in enumerate(zip(rom.read_bytes(), image)) if a != b):
        raise ValueError('Unrelated game mutation')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():
            shutil.copy2(p, out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    (out/'engine.bin').write_bytes(engine)
    paths = [Path(__file__), Path('tests/test_compact_startup_pitch.py'),
             Path('tools/build_startup_pitch_trial.py'), Path('tools/build_inline_pitch_trial.py'),
             parent/'manifest.json', rom, out/'engine.bin', out/'native-cpu.sfc']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), spc_sha256=sha(out/'engine.bin'),
        experimental_startup_pitch=dict(detail, parent=str(parent), release_ready=False,
            sources={str(p): sha(p) for p in paths}))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=meta['rom_sha256'], spc_sha256=meta['spc_sha256'], **detail)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
