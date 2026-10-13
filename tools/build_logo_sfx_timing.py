"""Trial 4305e: start the splash ident SFX on the first reveal frame.

Before: the struktured labs splash (bank $D1) only began sending the ident
curve (pitch/volume/sequence to $2140-$2143, which keys the SFX on) in the
hold loop, after the 168-frame reveal, so the sound started when the logo
was already fully drawn.

After: the curve sender is a subroutine at $D1:0810 called once per VBlank
from the very first reveal frame (screen on, edge 0) onwards; the reveal
step at $D1:0800 waits through it too. The reveal timing (+3 every 2
frames, 168 frames) and the 240-frame hold are unchanged. The 240-entry
curve (4 s, ends at volume 0) therefore finishes 72 frames into the hold;
after that the sender does nothing and the hold's key-off/IPL handoff runs
as before.

usage: python3 -m tools.build_logo_sfx_timing --parent ROM --out ROM
"""
import argparse, hashlib, json
from pathlib import Path
from tools.build_inline_pitch_trial import checksum

D1 = 0x110000
SEND = 0x0810          # send_vblank; SEND+3 = send
INIT = 0x0840


def patch(img, at, old, new):
    old = bytes.fromhex(old) if isinstance(old, str) else old
    new = bytes.fromhex(new) if isinstance(new, str) else new
    assert len(old) == len(new), (hex(at), len(old), len(new))
    assert img[D1 + at:D1 + at + len(old)] == old, (hex(at), img[D1 + at:D1 + at + len(old)].hex())
    img[D1 + at:D1 + at + len(new)] = new


def find(img, pat, start=0, end=0x800):
    i = img.find(bytes.fromhex(pat), D1 + start, D1 + end)
    assert i >= 0, pat
    assert img.find(bytes.fromhex(pat), i + 1, D1 + end) < 0, ('ambiguous', pat)
    return i - D1


def build(parent, out):
    img = bytearray(parent.read_bytes())
    # pre-reveal: lda #1, sta $1FF0, stz $1FF1, jsr next_vblank, lda #$0F, sta $2100
    pre = find(img, 'a9018df01f9cf11f20ca01a90f8d0021')
    patch(img, pre + 8, '20ca01', '204008')                      # jsr init (X/$1FF2/$1FF3 = 0, vblank)
    # @reveal top: jsr next_vblank -> jsr send_vblank
    rev = find(img, '20ca01adf11fc9fcf00b2000088df11f8d272180eb')
    patch(img, rev, '20ca01', '201008')
    # reveal step3 (pha, jsr next_vblank, pla, clc, adc #3, rts): wait through send too
    patch(img, 0x0800, '4820ca016818690360', '4820100868186903' '60')
    # hold: drop the X/$1FF2/$1FF3 reset (curve continues), keep Y=240 frames
    hold = find(img, 'a200009cf21f9cf31fa0f000')
    patch(img, hold, 'a200009cf21f9cf31f', 'ea' * 9)
    body = ('20ca01bf5f02d18d4021bf6002d18d4121bf6102d18d4321'
            'eef31fadf31f8d4221e8e8e8eef21f88d0d6')
    hf = find(img, body)
    patch(img, hf, body, '20100888d0fa' + '8022' + 'ea' * 34)
    sub = bytes.fromhex(
        '20ca01'            # send_vblank: jsr next_vblank
        'adf21f' 'c9f0' 'b024'  # send: lda $1FF2 / cmp #240 / bcs done
        'bf5f02d1' '8d4021'
        'bf6002d1' '8d4121'
        'bf6102d1' '8d4321'
        'eef31f' 'adf31f' '8d4221'
        'e8e8e8' 'eef21f'
        '60')               # done: rts
    assert sub[10 + sub[9]] == 0x60 and len(sub) == 47, len(sub)
    patch(img, SEND, b'\xff' * len(sub), sub)
    init = bytes.fromhex('a20000' '9cf21f' '9cf31f' '4cca01')
    patch(img, INIT, b'\xff' * len(init), init)
    checksum(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img)
    print(json.dumps(dict(out=str(out), sha256=hashlib.sha256(img).hexdigest())))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
