"""Trial: ending credits CHR fix, struktured labs credit page, slower splash reveal.

1. Ending credits (NES bank 13, SNES $C7). The credit page writer at NES $BA88
   selects the font CHR banks itself (MMC3 R0/R1 = the page entry's last word,
   $7A/$7E for text pages, $60/$62 for the Technos logo) with raw
   `STA $8000` / `STA $8001`. The trace-driven translator only rewrote mapper
   stores it saw executed, and no capture reached the ending, so these four
   stores stayed raw. On SNES they write to ROM and do nothing: BG tiles
   $80-$FF keep the last gameplay CHR, so lowercase story text and every staff
   credit draw from unrelated tiles (the "mirrored"/garbled red text). They
   now call the same in-bank mapper helpers ($622E select, $625D data) as
   every translated MMC3 store (e.g. fixed bank $FEC5).
2. struktured labs page. The staff loop ($B980) shows pages $1A = 0..$13 (page $12 is the Technos logo, $13 THE END)
   and then parks forever. JSR $BA21 at
   $B980 becomes JSR to a stub that, before page $12 (Technos Japan logo) only, draws one extra
   page with the normal text font and hold ($0518=$28, $B9C8 wait $10), then
   restores $1A=$12 and draws the Technos page as before; page $13 (THE END)
   follows unchanged. The extra page is
   drawn by a relocated copy of the page writer ($BA21-$BAA6) whose entry
   table base points at a private 10-byte entry, because every table slot
   past $13 is already used ($14 is the blank page the story loop clears
   with, $15+ overlap the blank text). Everything lives in the zero-filled
   $BF00-$BFFE tail of NES bank 13; $BFFF (bank id) is untouched.
3. Branding splash reveal ($D1). Old: window edge +4 per frame, 63 frames.
   New: +3 every 2 frames (84 steps, 168 frames, about 2.8 s). Final edge is
   still $FC then $FF; the hold is unchanged.
"""
import argparse, hashlib, json
from pathlib import Path
from tools.build_inline_pitch_trial import checksum

C7 = 0x70000          # SNES bank $C7 file base (HiROM)
D1 = 0x110000


def patch(img, at, old, new):
    assert img[at:at + len(old)] == old, (hex(at), img[at:at + len(old)].hex())
    img[at:at + len(new)] = new


def row(text):
    assert len(text) <= 26
    lead = (26 - len(text)) // 2
    body = bytes(0 if c == ' ' else 0x90 + ord(c) - 65 for c in text)
    return bytes(lead) + body + bytes(26 - lead - len(body))


LINE1, LINE2 = 'SNES PORT BY', 'STRUKTURED LABS'
TEXT1, TEXT2, ENTRY, STUB = 0xBF00, 0xBF1A, 0xBF34, 0xBF3E
CLONE = 0xBF5C
BLANK = 0xBB8F


def build(parent, out):
    img = bytearray(parent.read_bytes())
    # 1. raw MMC3 stores in the credit page writer
    for a, new in ((0xBA92, '202e62'), (0xBA98, '205d62'), (0xBA9D, '202e62'), (0xBAA3, '205d62')):
        patch(img, C7 + a, bytes.fromhex('8d0080' if new == '202e62' else '8d0180'), bytes.fromhex(new))
    # 2. struktured labs page
    patch(img, C7 + TEXT1, bytes(52), row(LINE1) + row(LINE2))
    w = lambda v: bytes((v & 255, v >> 8))
    patch(img, C7 + ENTRY, bytes(10), w(BLANK) + w(TEXT1) + w(BLANK) + w(TEXT2) + bytes.fromhex('7e7a'))
    writer = bytearray(img[C7 + 0xBA21:C7 + 0xBAA7])
    refs = [i for i in range(len(writer) - 2) if writer[i] == 0xB9 and writer[i + 2] == 0xBA
            and writer[i + 1] in (0xBD, 0xBE)]
    assert len(refs) == 4, refs           # text pointer lo/hi, CHR word lo/hi
    for i in refs:
        writer[i + 1:i + 3] = w(ENTRY + writer[i + 1] - 0xBD)
    assert len(writer) == 0x86 and CLONE + len(writer) <= 0xBFFF
    patch(img, C7 + CLONE, bytes(len(writer)), bytes(writer))
    stub = (bytes.fromhex('a51a c912 d015 a900 851a'.replace(' ', '')) + b'\x20' + w(CLONE) +
            bytes.fromhex('a928 8d1805 a910 20c8b9 a912 851a 4c21ba'.replace(' ', '')))
    assert len(stub) == 30 and STUB + 30 <= CLONE
    patch(img, C7 + STUB, bytes(len(stub)), stub)
    patch(img, C7 + 0xB980, bytes.fromhex('2021ba'), bytes([0x20]) + w(STUB))
    # 3. splash reveal: JSR step3 (pha, jsr next_vblank, pla, clc, adc #3, rts)
    patch(img, D1 + 0x0800, b'\xff' * 9, bytes.fromhex('4820ca016818690360'))
    patch(img, D1 + 0x00DC, bytes.fromhex('adf11fc9fcf00b186904'), bytes.fromhex('adf11fc9fcf00b200008'))
    checksum(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img)
    print(json.dumps(dict(out=str(out), sha256=hashlib.sha256(img).hexdigest())))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
