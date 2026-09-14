"""Finalize/check the project's power-of-two LoROM test images."""
import argparse
from pathlib import Path
import struct


def verify(data):
    size = len(data)
    if size < 32768 or size > 4194304 or size & (size - 1):
        raise ValueError("Expected a power-of-two LoROM image, 32 KiB to 4 MiB")
    if data[0x7fd5:0x7fd8] != bytes((0x20, 0, size.bit_length() - 11)):
        raise ValueError("LoROM header size does not match image")
    complement, checksum = struct.unpack_from("<HH", data, 0x7fdc)
    if checksum ^ complement != 0xffff or sum(data) & 0xffff != checksum:
        raise ValueError("Invalid SNES checksum")
    reset, = struct.unpack_from("<H", data, 0x7ffc)
    if reset != 0x8000 or data[0] != 0x78:
        raise ValueError("Invalid reset vector/opcode")


def finalize(data):
    if len(data) < 32768:
        raise ValueError("Truncated LoROM")
    result = bytearray(data)
    result[0x7fdc:0x7fe0] = b"\xff\xff\0\0"
    checksum = sum(result) & 0xffff
    struct.pack_into("<HH", result, 0x7fdc, checksum ^ 0xffff, checksum)
    verify(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        verify(args.rom.read_bytes())
    else:
        args.rom.write_bytes(finalize(args.rom.read_bytes()))
