"""Trial 4305f: complete BG republish on every scene load (issue #8).

Mechanism (see docs/ROOM-ENTRY-BG-4305F.md):
- The NES $2007 adapter skips a write whose byte already equals the
  nametable shadow (`cmp [$00] / beq @unchanged`), so a row is only marked
  dirty when its shadow bytes change.
- At the rendering-on edge of a load ($1CA0 1 -> 2) the transition snapshot
  kept every CLEAN row (state 0) as "already in VRAM" and only required the
  dirty ones. The SNES-side CHR cache ($1DA0, 24 slots) likewise skips a
  bank whose number did not change.
- So any VRAM tilemap/CHR content that differs from the shadow while its row
  is marked clean (a dropped or partial upload; real hardware ignores VRAM
  writes outside VBlank/forced blank) survives every later scene load for all
  cells whose bytes happen to match the previous scene, and the whole scene
  when the game rewrites identical data. Only a screen that first writes
  different bytes over the playfield (the pause submenus) repairs it.
Fix, in all eight runtime banks:
1. render-on snapshot: every visible row (0-29 of each table) becomes
   state 1 + required, exactly what a pattern-table change already did
   (`lda $05 / bne rebuild` -> `bra rebuild`).
2. transition start hook ($7F80, `sta $1CA0`): also invalidates the 24-slot
   CHR bank cache ($1DA0-$1DB7 = $FF) and raises the CHR-dirty gate ($1CBB),
   so every BG/OBJ CHR slot is re-uploaded before the transition barrier
   (transition_ready waits for rows AND CHR jobs) unblanks the screen.
All uploads happen inside the existing forced-blank transition publisher.

usage: python3 -m tools.build_room_entry_bg --parent ROM --out ROM
"""
import argparse, hashlib, json
from pathlib import Path
from tools.build_inline_pitch_trial import checksum

PARENT_SHA = '6cac90a03db387b6e55a49d9987e3572ab2fe0ec070fef7b96f6b7f1e5f78229'
LOOP = 0x280C           # in each runtime bank: lda $05 / bne +7 / lda $1D00,x / cmp #3
HOOK = 0x7F80           # sta $1CA0 / php / pha ...
CALL = 0x2831           # jsr $7F80 (render-on edge only)
HELPER = 0x7FA0
HELPER_CODE = bytes.fromhex(
    '8da01c'            # sta $1CA0         (replaced instruction)
    '08' '48' 'da'      # php / pha / phx   (A8/X8, E=1 or native: 8-bit ops only)
    'a217'              # ldx #23
    'a9ff'              # lda #$FF
    '9da01d'            # loop: sta $1DA0,x  (DB is a system-area mirror)
    'ca' '10fa'         # dex / bpl loop
    'a901' '8dbb1c'     # lda #1 / sta $1CBB (CHR-dirty gate)
    'fa' '68' '28'      # plx / pla / plp
    '60')               # rts


def patch(img, at, old, new):
    old = bytes.fromhex(old) if isinstance(old, str) else old
    new = bytes.fromhex(new) if isinstance(new, str) else new
    assert len(old) == len(new)
    assert img[at:at + len(old)] == old, (hex(at), img[at:at + len(old)].hex())
    img[at:at + len(new)] = new


def build(parent, out):
    img = bytearray(parent.read_bytes())
    assert hashlib.sha256(img).hexdigest() == PARENT_SHA, 'parent must be 4305e'
    for bank in range(1, 9):
        b = bank * 0x10000
        patch(img, b + CALL, '20807f', '20807f')                  # guard: sole caller
        patch(img, b + LOOP, 'a505d007bd001dc903d002a901', 'a5058007bd001dc903d002a901')
        patch(img, b + HOOK, '8da01c0848', '20a07f0848')
        patch(img, b + HELPER, b'\xff' * len(HELPER_CODE), HELPER_CODE)
    checksum(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img)
    print(json.dumps(dict(out=str(out), sha256=hashlib.sha256(img).hexdigest())))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
