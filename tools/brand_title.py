"""Opt-in first-pass SNES branding using the original game's menu font.

Replaces the mode-selection instruction, not original authorship credits.
No CHR, palette, executable instruction, or gameplay text is changed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

OFFSET = 0x4B9FE  # Original PRG $F9FE, mapped into C4:B9FE.
ORIGINAL = bytes.fromhex('d2dee5dedced00e0dae6de00e6e8ddde00b900dce1daebdadceddeebb6')
LABEL = 'SNES PORT BY STRUKTURED LABS.'
SOURCE_SHA = 'b95f8def04c0012604b7cc68cf4ed8f49b2dfe4beda6182051de4b2423bea7b1'


def encode(text):
    font = {chr(ord('A') + i): 0xC0 + i for i in range(26)}
    font.update({' ': 0, '.': 0xB6})
    try:
        return bytes(font[c] for c in text)
    except KeyError as exc:
        raise ValueError('Unsupported title glyph') from exc


def patch(image):
    if len(image) != 0x200000 or image[0xFFC0:0xFFD5] != b'RCR NATIVE CPU PROOF ':
        raise ValueError('Expected the native 2 MiB RCR cartridge')
    complement, checksum = struct.unpack_from('<HH', image, 0xFFDC)
    if complement ^ checksum != 0xFFFF or sum(image) & 0xFFFF != checksum:
        raise ValueError('Invalid input checksum')
    if image[OFFSET:OFFSET + len(ORIGINAL)] != ORIGINAL or image.count(ORIGINAL) != 1:
        raise ValueError('Menu instruction preimage mismatch or ambiguous target')
    replacement = encode(LABEL)
    if len(replacement) != len(ORIGINAL):
        raise ValueError('Branding must preserve the original string length')
    result = bytearray(image)
    result[OFFSET:OFFSET + len(ORIGINAL)] = replacement
    result[0xFFDC:0xFFE0] = b'\xff\xff\0\0'
    checksum = sum(result) & 0xFFFF
    struct.pack_into('<HH', result, 0xFFDC, checksum ^ 0xFFFF, checksum)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True, help='Native build directory')
    parser.add_argument('--out', type=Path, required=True, help='New opt-in output directory')
    args = parser.parse_args()
    source = args.candidate / 'native-cpu.sfc'
    data = source.read_bytes()
    manifest = json.loads((args.candidate / 'manifest.json').read_text())
    if manifest['source_rom_sha256'] != SOURCE_SHA or manifest['rom_sha256'] != hashlib.sha256(data).hexdigest():
        raise ValueError('Candidate manifest does not bind this original ROM and cartridge')
    branded = patch(data)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'native-cpu.sfc').write_bytes(branded)
    manifest.update(rom_sha256=hashlib.sha256(branded).hexdigest(), branding={
        'label': LABEL, 'original_label': 'Select game mode & character.',
        'parent_rom_sha256': hashlib.sha256(data).hexdigest(),
        'offset': OFFSET, 'length': len(ORIGINAL),
        'scope': 'Opt-in mode-selection footer only; original credits and all CHR unchanged',
        'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    })
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest['branding'], indent=2))


if __name__ == '__main__':
    main()
