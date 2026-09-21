"""Isolated opt-in in-ROM AI P2 and P1-to-P2 management prototype."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

SLOT, SIZE = 0x6900, 0x700
HOOK = 0xfd8e


def patch(original, helper, poll):
    if len(original) != 0x200000 or len(helper) != SIZE:
        raise ValueError('Wrong ROM/helper extent')
    old = b'\x4c'+poll.to_bytes(2, 'little')
    image = bytearray(original)
    allowed = set(range(0xffdc, 0xffe0))
    for bank in range(1, 9):
        at, hook = bank*65536+SLOT, bank*65536+HOOK
        if original[at:at+SIZE] != b'\xff'*SIZE:
            raise ValueError('Occupied AI helper slot')
        if original[hook:hook+3] != old:
            raise ValueError('Changed joypad entry')
        image[at:at+SIZE] = helper
        image[hook:hook+3] = b'\x4c'+SLOT.to_bytes(2, 'little')
        allowed.update(range(at, at+SIZE)); allowed.update(range(hook, hook+3))
    checksum(image)
    if any(i not in allowed for i, (a,b) in enumerate(zip(original,image)) if a != b):
        raise ValueError('Unrelated ROM mutation')
    return image


def build(parent, out):
    if out.exists(): raise ValueError('Fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256'] or meta['experimental_control_presets']:
        raise ValueError('Need bound legacy nine-bit pad adapter')
    poll = labels(parent/'native_runtime.lbl')['native_joypad_poll']
    out.mkdir(parents=True)
    # Only needed cartridge provenance, not hundreds of unrelated objects.
    for name in ('native_runtime.lbl', 'native_boot.lbl'):
        shutil.copy2(parent/name, out/name)
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'POLL={poll}',
        '-o', str(out/'ai-p2.o'), 'snes/ai_p2.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/ai_p2.cfg',
        '-Ln', str(out/'ai-p2.lbl'), '-o', str(out/'ai-p2.bin'), str(out/'ai-p2.o')], check=True)
    image = patch(rom.read_bytes(), (out/'ai-p2.bin').read_bytes(), poll)
    (out/'native-cpu.sfc').write_bytes(image)
    files = [Path(__file__),Path('snes/ai_p2.asm'),Path('snes/ai_p2.cfg'),
        Path('tools/audio_packet_log.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),
        rom,parent/'manifest.json',parent/'native_runtime.lbl',out/'ai-p2.bin']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_ai_p2=dict(
        parent=str(parent), enabled_by_default=False, helper=SLOT, size=SIZE,
        state_address='7ff000', state_size=32,
        sources={str(p):sha(p) for p in files},release_ready=False,
        controls='Select original 2P. Tap R on pregame settings or in-game to toggle AI. '
                 'Hold P1 L to drive P2 belongings/equipment; Start remains original global P1 pause. '
                 'Release L for one neutral poll, then P1+AI resume. Physical P2 input overrides AI.',
        limits='Lane-first follow and stuck detours. HUD AI label while enabled. '
               'No friendly-fire guarantee, shopping AI or persistence. '
               'Not compatible yet with experimental control presets.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
