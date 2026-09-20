"""Replay physical commands with the latest cartridge's checked receiver-dispatch engine.

Only the pre-existing two-byte receiver jump optimization and checksum may change.
This is a cold, frame-quantized diagnostic, not a game or a physical DSP snapshot.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_receiver_dispatch_trial import patch


def replace(image, original, candidate, layout, poll):
    expected, detail = patch(original, layout, poll)
    if expected != candidate:
        raise ValueError('Candidate is not exactly the checked dispatch change')
    if len(image) != 0x200000 or image[0x120000:0x120000+len(original)] != original:
        raise ValueError('Different player engine placement')
    changed = bytearray(image)
    changed[0x120000:0x120000+len(candidate)] = candidate
    checksum(changed)
    allowed = {0x120000+i for i, (a, b) in enumerate(zip(original, candidate)) if a != b}
    if len(allowed) != 2:
        raise ValueError('Expected exactly two engine operand bytes')
    allowed.update(range(0xffdc, 0xffe0))
    if any(i not in allowed for i, (a, b) in enumerate(zip(image, changed)) if a != b):
        raise ValueError('Unrelated replay changes')
    return bytes(changed), detail


def build(fixture, candidate, out):
    if out.exists():
        raise ValueError('Fresh output required')
    spec = bound_report(fixture/'manifest.json')
    meta = json.loads((candidate/'manifest.json').read_text())
    rom = candidate/'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256'] or sha(fixture/'player.sfc') != spec['rom_sha256']:
        raise ValueError('Unbound cartridge')
    original = (fixture/'engine.bin').read_bytes()
    if hashlib.sha256(original).hexdigest() != spec['spc_sha256']:
        raise ValueError('Unbound original engine')
    at, size = meta['sweep_driver_rom_offset'], meta['sweep_driver_layout']['engine_bytes']
    engine = rom.read_bytes()[at:at+size]
    if hashlib.sha256(engine).hexdigest() != meta['spc_sha256']:
        raise ValueError('Unbound candidate engine')
    image, detail = replace((fixture/'player.sfc').read_bytes(), original, engine,
                            meta['sweep_driver_layout'], meta['receiver_poll'])
    shutil.copytree(fixture, out)
    (out/'engine.bin').write_bytes(engine)
    (out/'player.sfc').write_bytes(image)
    spec.update(rom_sha256=sha(out/'player.sfc'), spc_sha256=sha(out/'engine.bin'),
        engine_source_rom_sha256=meta['rom_sha256'], mutation='receiver-dispatch-only',
        dispatch_change=detail, scope=__doc__, release_ready=False)
    # source_rom_sha256 still identifies the physical command source, not the new engine.
    paths = [Path(__file__), Path('tools/build_receiver_dispatch_trial.py'),
        Path('tools/build_inline_pitch_trial.py'), fixture/'manifest.json',
        candidate/'manifest.json', rom, out/'engine.bin', out/'player.sfc', out/'stream.bin']
    spec['sources'].update({str(p): sha(p) for p in paths})
    (out/'manifest.json').write_text(json.dumps(spec, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=spec['rom_sha256'], spc_sha256=spec['spc_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('fixture', 'candidate', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
