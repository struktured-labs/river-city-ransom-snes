"""Trial: Gamer item-consume caps 127 (stats 0-7) + password encoder clamp to 6 bits.

Item consume (NES PRG $9240-$9332, bank 2 -> SNES $C3) caps every stat via
`CMP/LDA $936D,X` (63 for stats 0-7, 127 max power). Gamer docs promise 127;
these JSRs return $7F when $064C==3. The NES password encoder ($BE14, bank 3
-> $C4) copies stats 0-7 raw into 6-bit glyph slots, so any value >63 makes
an out-of-alphabet glyph (#28). The hook clamps those 8 slots to 63 (lossy for
Gamer, always re-enterable). Stamina/max power keep their original 8 bits.
"""
import argparse, hashlib, json
from pathlib import Path
from tools.build_inline_pitch_trial import checksum


def patch(img, at, old, new):
    assert img[at:at + len(old)] == old, hex(at)
    img[at:at + len(new)] = new


def build(parent, out):
    img = bytearray(parent.read_bytes())
    # $C3:7700 cap_cmp, $C3:7711 cap_lda
    cap = bytes.fromhex('48 AD4C06 C903 F005 68 DD6D93 60 68 C97F 60'
                        ' AD4C06 C903 F004 BD6D93 60 A97F 60')
    assert len(cap) == 0x1F
    patch(img, 0x37700, b'\xff' * len(cap), cap)
    patch(img, 0x392FA, bytes.fromhex('dd6d93'), bytes.fromhex('200077'))
    patch(img, 0x39301, bytes.fromhex('bd6d93'), bytes.fromhex('201177'))
    patch(img, 0x39306, bytes.fromhex('bd6d93'), bytes.fromhex('201177'))
    # $C4:7700 clamp the eight 6-bit stat slots $058E..$0595,X
    clamp = b''
    for k in range(8):
        lo = 0x8E + k
        clamp += bytes([0xBD, lo, 0x05, 0xC9, 0x40, 0x90, 0x02, 0xA9, 0x3F, 0x9D, lo, 0x05])
    clamp += bytes.fromhex('B9BF04 60')
    patch(img, 0x47700, b'\xff' * len(clamp), clamp)
    patch(img, 0x4BE44, bytes.fromhex('b9bf04'), bytes.fromhex('200077'))
    checksum(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img)
    print(json.dumps(dict(out=str(out), sha256=hashlib.sha256(img).hexdigest())))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
