"""Per-weapon, damage-scaled rumble on a ROM that already has the original
rumble helper (e.g. build/trial-gamer-downshift-4305c, no manifest).

Re-assembles snes/rumble.asm (main slot $6B00 plus the weapon areas $6D24
and $6F08, banks 1-8), replaces the old helper, re-points its three hooks,
and adds the damage latch at bank 5 $8CF4. The old helper's labels come from
the committed snes/rumble.asm at OLD_REV, assembled the same way, and the
parent's slot must hold exactly those bytes.

usage: python3 -m tools.build_weapon_rumble --parent ROM --out DIR
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from tools.build_inline_pitch_trial import checksum
from tools.build_rumble import assemble, patch_image, SLOT, SIZE
from tools.rumble_pulses import pulse_table, weapon_table

OLD_REV = '838fc5b'


def old_helper(work):
    (work / 'old').mkdir()
    for f in ('snes/rumble.asm', 'snes/rumble.cfg'):
        (work / 'old' / Path(f).name).write_bytes(
            subprocess.run(['git', 'show', f'{OLD_REV}:{f}'], check=True, capture_output=True).stdout)
    o = work / 'old'
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(o / 'r.o'), str(o / 'rumble.asm')], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', str(o / 'rumble.cfg'), '-Ln', str(o / 'r.lbl'),
                    '-o', str(o / 'r.bin'), str(o / 'r.o')], check=True)
    names = {}
    for line in (o / 'r.lbl').read_text().splitlines():
        f = line.split()
        if len(f) >= 3 and f[2].startswith('.'):
            names[f[2][1:]] = int(f[1], 16)
    return (o / 'r.bin').read_bytes(), names


SENT_STORE = bytes.fromhex('8f07f87e')          # sta f:R_SENT -> jsr rumble_latch / nop
FINISH = bytes.fromhex('a9ff8f014200')          # lda #$FF / sta f:WRIO -> lda #$FF / jsr rumble_finish / nop


def autojoy_sites(helper):
    """The two helper stores build_autojoy_compat (4299) re-routes."""
    a, b = helper.find(SENT_STORE), helper.find(FINISH)
    if a < 0 or b < 0 or helper.count(SENT_STORE) != 1 or helper.count(FINISH) != 1:
        raise ValueError('Autojoy sites not unique in the helper')
    return a, b + 2


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    src = parent.read_bytes()
    work = Path(tempfile.mkdtemp(prefix='wrumble-'))
    old, old_names = old_helper(work)
    # The parent has build_autojoy_compat's two re-routes in the helper: take
    # them from bank 1 and require old helper + re-routes in every bank.
    oa, ob = autojoy_sites(old)
    p1 = src[0x10000 + SLOT:0x10000 + SLOT + SIZE]
    ra, rb = p1[oa:oa + 4], p1[ob:ob + 4]
    if ra[0] != 0x20 or rb[0] != 0x20 or ra[3] != 0xEA or rb[3] != 0xEA:
        raise ValueError('Parent helper lacks the autojoy re-routes')
    want = bytearray(old)
    want[oa:oa + 4], want[ob:ob + 4] = ra, rb
    for bank in range(1, 9):
        if src[bank * 65536 + SLOT:bank * 65536 + SLOT + SIZE] != want:
            raise ValueError(f'Parent bank {bank} does not hold the {OLD_REV} rumble helper (+autojoy)')
    helper, parts, names = assemble(work)
    na, nb = autojoy_sites(helper)
    main = bytearray(helper)
    main[na:na + 4], main[nb:nb + 4] = ra, rb
    parts[0] = (SLOT, bytes(main))
    image = bytearray(src)
    allowed = patch_image(image, parts, names, replace=old_names)
    checksum(image)
    if any(i not in allowed for i, (a, b) in enumerate(zip(src, image)) if a != b):
        raise ValueError('Unrelated ROM mutation')
    out.mkdir(parents=True)
    (out / 'native-cpu.sfc').write_bytes(image)
    for n in ('rumble.o', 'rumble.bin', 'rumble.lbl'):
        shutil.move(str(work / n), out / n)
    shutil.rmtree(work)
    digest = hashlib.sha256(image).hexdigest()
    (out / 'manifest.json').write_text(json.dumps(dict(
        rom_sha256=digest, parent=str(parent), parent_rom_sha256=hashlib.sha256(src).hexdigest(),
        weapon_rumble=dict(areas=[f'${a:04X}+{len(d):#x}' for a, d in parts], ram='$7EF800-$7EF80D',
                           labels={k: hex(v) for k, v in names.items()},
                           pulses=[dict(event=e, strong=s, weak=w, frames=f) for e, s, w, f in pulse_table()],
                           weapons=[dict(zip(('weapon', 'strong', 'weak', 'frames', 'envelope'), r))
                                    for r in weapon_table()])), indent=2) + '\n')
    used = [len(d.rstrip(b'\xff')) for _, d in parts]
    print(json.dumps(dict(out=str(out), rom_sha256=digest, used=used)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
