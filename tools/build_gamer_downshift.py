"""Trial: clamp stats when the difficulty mode leaves Gamer (see snes/gamer_downshift.asm).

menu_apply (difficulty helper, $70FA in each replica, banks $C1-$C8) is the
only in-game writer of $064C (load_sram only runs at power-on). Its
"nop; sta a:$064C" becomes "jsr clamp_sta; nop"; clamp_sta is placed at
$7300 in every replica (free $FF there in all eight banks). cap_gain goes to
$C3:7342 and replaces the second cap_lda JSR of the item-consume code
(NES $9306, file $39306), the one that feeds the shown gain.
"""
import argparse, hashlib, json, subprocess
from pathlib import Path
from tools.build_inline_pitch_trial import checksum

ROOT = Path(__file__).resolve().parents[1]


def patch(img, at, old, new):
    assert img[at:at + len(old)] == old, (hex(at), img[at:at + len(old)].hex())
    img[at:at + len(new)] = new


def assemble(work):
    work.mkdir(parents=True, exist_ok=True)
    cc = ROOT / '.deps/cc65/bin'
    subprocess.run([str(cc / 'ca65'), '-o', str(work / 'gds.o'), str(ROOT / 'snes/gamer_downshift.asm')], check=True)
    subprocess.run([str(cc / 'ld65'), '-C', str(ROOT / 'snes/gamer_downshift.cfg'), '-o', str(work / 'gds.bin'),
                    '-Ln', str(work / 'gds.lbl'), str(work / 'gds.o')], check=True)
    labels = {l.split()[2].lstrip('.'): int(l.split()[1], 16) for l in (work / 'gds.lbl').read_text().split('\n') if l}
    return (work / 'gds.bin').read_bytes().rstrip(b'\xff'), labels


def build(parent, out):
    img = bytearray(parent.read_bytes())
    code, lab = assemble(out.parent / 'asm')
    assert lab['clamp_sta'] == 0x7300 and lab['cap_gain'] == 0x7342 and len(code) <= 0x80
    for bank in range(1, 9):
        base = bank * 0x10000
        patch(img, base + 0x7300, b'\xff' * len(code), code)
        patch(img, base + 0x70FA, bytes.fromhex('ea8d4c06'), bytes.fromhex('200073ea'))
    patch(img, 0x39306, bytes.fromhex('201177'), bytes.fromhex('204273'))
    checksum(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img)
    print(json.dumps(dict(out=str(out), sha256=hashlib.sha256(img).hexdigest())))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    build(**vars(p.parse_args()))
