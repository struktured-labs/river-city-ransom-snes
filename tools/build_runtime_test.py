"""Assemble an asset-free SNES cartridge testing the production native adapter."""
from pathlib import Path
import struct
import subprocess

try:
    from .build_native import stub
except ImportError:
    from build_native import stub

ROOT = Path(__file__).resolve().parents[1]


def build(out, controllers=False, jump=False):
    out.mkdir(parents=True, exist_ok=True)
    ca65, ld65 = [str(ROOT / ".deps/cc65/bin" / name) for name in ("ca65", "ld65")]
    subprocess.run([ca65, "-D", "video_prepare_bridge=32512", "-g", "-o", str(out / "runtime.o"), str(ROOT / "snes/native_runtime.asm")], check=True)
    subprocess.run([ld65, "-C", str(ROOT / "snes/native_runtime.cfg"), "-Ln", str(out / "runtime.lbl"),
                    "-o", str(out / "runtime.bin"), str(out / "runtime.o")], check=True)
    symbols = {line.split()[2].lstrip("."): int(line.split()[1], 16)
               for line in (out / "runtime.lbl").read_text().splitlines()}
    io_stub = stub(0x8D, 0x2007, symbols['dispatch_ppudata'], fast_ppudata=True)
    read_address = 24576 + len(io_stub)
    io_stub += stub(0xAD, 0x2007, symbols['dispatch_ppudata_read'], fast_ppudata=True)
    subprocess.run([ca65, *(["-D", "CONTROLLER_TEST=1"] if controllers or jump else []), *(["-D", "JUMP_TEST=1"] if jump else []), "-D", f'dispatch_read={symbols["dispatch_read"]}',
                    "-D", f'dispatch_write={symbols["dispatch_write"]}',
                    "-D", f'bank_switch_enter={symbols["bank_switch_enter"]}',
                    '-D', f'bulk_ppu_byte={symbols["bulk_ppu_byte"]}',
                    '-D', f'bulk_source_byte={symbols["bulk_source_byte"]}',
                    "-D", 'io_write_stub=24576', '-D', f'io_read_stub={read_address}', "-o", str(out / "test.o"),
                    str(ROOT / "snes/runtime_test.asm")], check=True)
    subprocess.run([ld65, "-C", str(ROOT / "snes/native_boot.cfg"), "-o", str(out / "test.bin"),
                    str(out / "test.o")], check=True)
    image = bytearray(b"\xff" * 2097152)
    # Count producer-bridge calls without running graphics in the ABI fixture.
    image[0x7F00:0x7F04] = bytes.fromhex('ee8e1c6b')  # INC $1C8E; RTL
    program = (out / "test.bin").read_bytes()
    image[0x8000:0x10000] = program
    for bank in range(1, 9):
        image[bank * 0x10000 + 0x8000:(bank + 1) * 0x10000] = program
        image[bank * 0x10000 + 0x2000:bank * 0x10000 + 0x6000] = (out / "runtime.bin").read_bytes()
        image[bank * 0x10000 + 0xBFFF] = bank - 1
        image[bank * 0x10000 + 0x6000:bank * 0x10000 + 0x6000 + len(io_stub)] = io_stub
    for bank in range(128):
        image[0xF0000 + bank * 1024 + 0x15] = bank ^ 0x91
    image[0xFFDC:0xFFE0] = b"\xff\xff\0\0"
    checksum = sum(image) & 65535
    struct.pack_into("<HH", image, 0xFFDC, checksum ^ 65535, checksum)
    (out / "adapter-test.sfc").write_bytes(image)
    print(out / "adapter-test.sfc")


if __name__ == "__main__":
    build(ROOT / "build/runtime-test")
