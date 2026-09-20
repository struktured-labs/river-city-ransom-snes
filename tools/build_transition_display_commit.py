"""Keep room transition pending until the final palette/display batch is admitted."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA = '4393594cd1d601c72f75efba238519c1e7dcea6b63ce758fc45a8f2ff9747e21'
HOOK = 0x8457
PREIMAGE = bytes.fromhex('20e68620c886b00160')
HELPER = 0x7340


def assemble():
    with tempfile.TemporaryDirectory(prefix='rcr-transition-commit-') as temp:
        obj = Path(temp)/'helper.o'; binary = Path(temp)/'helper.bin'
        subprocess.run(['.deps/cc65/bin/ca65', '-o', str(obj),
                        'snes/transition_display_commit.asm'], check=True)
        subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/transition_display_commit.cfg',
                        '-o', str(binary), str(obj)], check=True)
        return binary.read_bytes()


def patch(image, helper):
    if hashlib.sha256(image).hexdigest() != PARENT_SHA:
        raise ValueError('Need exact early-OAM final-slack parent3479')
    if (image[HOOK:HOOK+len(PREIMAGE)] != PREIMAGE or
            image[HELPER:HELPER+64] != b'\xff'*64 or not 0 < len(helper) <= 64):
        raise ValueError('Changed entry, occupied padding or invalid helper')
    data = bytearray(image)
    data[HOOK:HOOK+len(PREIMAGE)] = bytes.fromhex('4c4073')+b'\xea'*6
    data[HELPER:HELPER+len(helper)] = helper
    checksum(data)
    changes = [i for i, (a,b) in enumerate(zip(image, data)) if a != b]
    allowed = set(range(HOOK, HOOK+len(PREIMAGE))) | set(range(HELPER, HELPER+len(helper))) | set(range(0xffdc,0xffe0))
    if any(i not in allowed for i in changes):
        raise ValueError('Unrelated mutation')
    return bytes(data), changes


def build(parent, out):
    started = time.monotonic()
    if out.exists(): raise ValueError('Fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    if meta['rom_sha256'] != sha(parent/'native-cpu.sfc'):
        raise ValueError('Parent manifest mismatch')
    if any(meta.get(k) for k in ('experimental_transition_game_first','experimental_transition_wait_prepare')):
        raise ValueError('Readiness has additional transition side effects')
    helper = assemble(); image, changes = patch((parent/'native-cpu.sfc').read_bytes(), helper)
    paths = [Path(__file__), Path('snes/transition_display_commit.asm'),
             Path('snes/transition_display_commit.cfg'), Path('tools/build_inline_pitch_trial.py'),
             Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65'),
             parent/'native-cpu.sfc', parent/'manifest.json']
    sources = {str(p):sha(p) for p in paths}
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file(): shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(image)
    (out/'transition-display-commit.bin').write_bytes(helper)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_transition_display_commit=dict(
        parent=str(parent), sources=sources, changed_offsets=changes,
        helper_hex=helper.hex(), build_seconds=time.monotonic()-started,
        release_ready=False, scope=__doc__+' Admission still uses unchanged beam cutoff254. '
        'Source transition state is restored on rejection; no gameplay, graphics or sound assets changed. '
        'Actual blank-duration, DMA, sprite, audio and speed regression checks remain required.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],helper_bytes=len(helper))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):parser.add_argument('--'+k,type=Path,required=True)
    build(**vars(parser.parse_args()))
