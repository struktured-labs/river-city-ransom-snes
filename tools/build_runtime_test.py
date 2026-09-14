"""Assemble an asset-free SNES cartridge testing the production native adapter."""
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def build(out):
    out.mkdir(parents=True, exist_ok=True)
    ca65, ld65 = [str(ROOT / ".deps/cc65/bin" / name) for name in ("ca65", "ld65")]
    subprocess.run([ca65, "-D", "video_prepare_bridge=32768", "-g", "-o", str(out / "runtime.o"), str(ROOT / "snes/native_runtime.asm")], check=True)
    subprocess.run([ld65, "-C", str(ROOT / "snes/native_runtime.cfg"), "-Ln", str(out / "runtime.lbl"),
                    "-o", str(out / "runtime.bin"), str(out / "runtime.o")], check=True)
    symbols = {line.split()[2].lstrip("."): int(line.split()[1], 16)
               for line in (out / "runtime.lbl").read_text().splitlines()}
    subprocess.run([ca65, "-D", f'dispatch_read={symbols["dispatch_read"]}',
                    "-D", f'dispatch_write={symbols["dispatch_write"]}', "-o", str(out / "test.o"),
                    str(ROOT / "snes/runtime_test.asm")], check=True)
    subprocess.run([ld65, "-C", str(ROOT / "snes/native_boot.cfg"), "-o", str(out / "test.bin"),
                    str(out / "test.o")], check=True)
    image = bytearray(b"\xff" * 2097152)
    program = (out / "test.bin").read_bytes()
    image[0x8000:0x10000] = program
    image[0x18000:0x20000] = program
    image[0x12000:0x16000] = (out / "runtime.bin").read_bytes()
    image[0xF0000 + 0x42 * 1024 + 0x15] = 0xD3
    image[0xFFDC:0xFFE0] = b"\xff\xff\0\0"
    checksum = sum(image) & 65535
    struct.pack_into("<HH", image, 0xFFDC, checksum ^ 65535, checksum)
    (out / "adapter-test.sfc").write_bytes(image)
    print(out / "adapter-test.sfc")


if __name__ == "__main__":
    build(ROOT / "build/runtime-test")
