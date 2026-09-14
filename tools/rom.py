"""Strict iNES inspection and lossless RCR asset preparation. No game supplied."""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import zlib

PRG_CRC = "78784cbf"
CHR_CRC = "204aa5eb"


def crc(data):
    return f"{zlib.crc32(data):08x}"


@dataclass(frozen=True)
class Rom:
    header: bytes
    prg: bytes
    chr: bytes
    mapper: int

    @classmethod
    def parse(cls, data):
        if len(data) < 16 or data[:4] != b"NES\x1a":
            raise ValueError("Expected a complete iNES header")
        h = data[:16]
        if h[7] & 0x0c:
            raise ValueError("Only clean iNES 1.0 headers are supported")
        if h[6] & 4:
            raise ValueError("Trainer-bearing ROMs are unsupported")
        if h[7] & 3 or any(h[10:]):
            raise ValueError("Unsupported console or dirty/reserved header bytes")
        if h[9] & ~1:
            raise ValueError("Invalid TV-system byte")
        prg_size, chr_size = h[4] * 16384, h[5] * 8192
        if not prg_size or len(data) != 16 + prg_size + chr_size:
            raise ValueError("ROM length does not match iNES bank counts")
        return cls(h, data[16:16 + prg_size], data[16 + prg_size:],
                   (h[6] >> 4) | (h[7] & 0xf0))

    def require_rcr_us(self):
        if self.mapper != 4 or len(self.prg) != 131072 or len(self.chr) != 131072:
            raise ValueError("RCR US requires mapper 4, 128 KiB PRG and 128 KiB CHR")
        if self.header[9] or self.header[6] & 0x0a or self.header[8] > 1:
            raise ValueError("Expected NTSC RCR without battery or four-screen VRAM")
        if crc(self.prg) != PRG_CRC or crc(self.chr) != CHR_CRC:
            raise ValueError("Unrecognized RCR revision: PRG/CHR checksums differ")

    def report(self):
        return {
            "mapper": self.mapper, "prg_bytes": len(self.prg), "chr_bytes": len(self.chr),
            "prg_crc32": crc(self.prg), "chr_crc32": crc(self.chr),
            "payload_sha256": hashlib.sha256(self.prg + self.chr).hexdigest(),
            "vectors": dict(zip(("nmi", "reset", "irq"),
                                (f"{v:04x}" for v in struct.unpack("<HHH", self.prg[-6:])))),
        }


def convert_chr(data, bpp=2):
    """Interleave the original two planes; zero-pad planes 2/3 for SNES OBJ."""
    if len(data) % 16 or bpp not in (2, 4):
        raise ValueError("CHR must contain complete 16-byte tiles; bpp must be 2 or 4")
    result = bytearray()
    for start in range(0, len(data), 16):
        tile = data[start:start + 16]
        for row in range(8):
            result.extend((tile[row], tile[row + 8]))
        if bpp == 4:
            result.extend(bytes(16))
    return bytes(result)


def prepare(rom, out):
    rom.require_rcr_us()
    # Create a new output directory only: never silently replace prior extraction.
    out.mkdir(parents=True, exist_ok=False)
    for i in range(16):
        (out / f"prg-{i:02x}.bin").write_bytes(rom.prg[i * 8192:(i + 1) * 8192])
    for i in range(128):
        bank = rom.chr[i * 1024:(i + 1) * 1024]
        (out / f"chr-{i:02x}-bg.bin").write_bytes(convert_chr(bank))
        (out / f"chr-{i:02x}-obj.bin").write_bytes(convert_chr(bank, 4))
    (out / "manifest.json").write_text(json.dumps(rom.report(), indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "prepare"))
    parser.add_argument("rom", type=Path)
    parser.add_argument("--out", type=Path, default=Path("build/assets"))
    args = parser.parse_args()
    try:
        rom = Rom.parse(args.rom.read_bytes())
        if args.command == "prepare":
            prepare(rom, args.out)
        print(json.dumps(rom.report(), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()
