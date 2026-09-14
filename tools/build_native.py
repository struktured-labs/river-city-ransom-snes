"""Build an experimental native CPU cartridge from verified execution coverage.

This is deliberately gated as a CPU integration experiment, not a released port.
Only instructions proven executed by the supplied source-ROM traces are patched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

try:
    from .rom import Rom, convert_chr
except ImportError:
    from rom import Rom, convert_chr

ROOT = Path(__file__).resolve().parents[1]
WRITES = {0x8D: "a", 0x8E: "x", 0x8C: "y", 0x9D: "a", 0x99: "a"}
READS = {0xAD: 0xAD, 0xAE: 0xAE, 0xAC: 0xAC, 0xBD: 0xAD, 0xB9: 0xAD, 0x2C: 0x2C}


def word(value):
    return struct.pack("<H", value)


def stub(opcode, operand, entry, resume=None, dynamic_apu=False):
    # Disable NMI before filling the shared mailbox. Otherwise an interrupt
    # can overwrite a half-written command or a just-returned read result.
    data = bytearray((0x9C, 0x00, 0x42, 0x08, 0x48))  # STZ $4200; PHP; PHA
    if opcode in WRITES:
        if WRITES[opcode] == "x":
            data.append(0x8A)
        elif WRITES[opcode] == "y":
            data.append(0x98)
        data += b"\x8d" + word(0x1B22)
    if dynamic_apu:
        data += b"\xad\xf9\x07\x8d" + word(0x1B20)
        data += b"\xad\xfa\x07\x8d" + word(0x1B21)
    elif opcode in (0x9D, 0xBD, 0x99, 0xB9):
        data.append(0x8A if opcode in (0x9D, 0xBD) else 0x98)
        data += bytes((0x18, 0x69, operand & 255, 0x8D)) + word(0x1B20)
        data += bytes((0xA9, operand >> 8, 0x69, 0, 0x8D)) + word(0x1B21)
    else:
        data += bytes((0xA9, operand & 255, 0x8D)) + word(0x1B20)
        data += bytes((0xA9, operand >> 8, 0x8D)) + word(0x1B21)
    data += b"\x22" + word(entry) + b"\xC1\x68\x28"  # JSL C1:handler; PLA PLP
    if opcode in READS:
        data += bytes((READS[opcode],)) + word(0x1B24)
    if resume is not None:
        if opcode != 0x8D or operand != 0x2000:
            raise ValueError("Only STA PPUCTRL supports the NMI-safe tail hook")
        # At this hardware enable write, stack shape exactly matches the NES.
        # Captured RCR PPUCTRL values use no SNES IRQ-enable bits ($10/$20).
        # The game also continues its menu/main tasks inside NMI handlers.
        # Always allow the NEXT NMI; only suppress an immediate same-VBlank one.
        # Inside an active game NMI, leave hardware NMI masked except for the
        # explicit FC60 coroutine wait (task $0100 == 0). No extra return frame.
        guard = b"\x08\x48\xad\x0a\x1c\xf0\x0a\xad\x00\x01\xf0\x05\x68\x28\x4c" + word(resume)
        return data + guard + b"\x68\x48\x29\x80\xf0\x05\xad\x12\x42\x30\xfb\x68\x28\x8d\x00\x42\x4c" + word(resume)
    return (data + b"\x08\x48\xad\x0a\x1c\xd0\x14\xad\x20\x1c\x29\x80\xf0\x0d"
            + b"\xad\x12\x42\x30\xfb\xad\x20\x1c\x29\x80\x8d\x00\x42\x68\x28\x60")


def build(rom_path, traces, out):
    original = rom_path.read_bytes()
    rom = Rom.parse(original)
    rom.require_rcr_us()
    sha = hashlib.sha256(original).hexdigest()
    deps = json.loads((ROOT / "tools/dependencies.json").read_text())
    engine = ROOT / ".deps/upernes" / deps["upernes"]["audio_path"]
    if hashlib.sha256(engine.read_bytes()).hexdigest() != deps["upernes"]["audio_sha256"]:
        raise ValueError("Unexpected SPC engine")
    out.mkdir(parents=True, exist_ok=False)
    rgb = Path("/usr/share/fceux/palettes/FCEUX.pal").read_bytes()
    colors = [(rgb[i] >> 3) | ((rgb[i + 1] >> 3) << 5) | ((rgb[i + 2] >> 3) << 10) for i in range(0, 192, 3)]
    (out / "native_palette.inc").write_text(".word " + ",".join(f"${n:04X}" for n in colors) + "\n")
    for name in ("native_boot", "native_runtime"):
        defines = []
        if name == "native_runtime":
            boot_symbols = {line.split()[2].lstrip("."): int(line.split()[1], 16)
                            for line in (out / "native_boot.lbl").read_text().splitlines()}
            defines = ["-D", f'video_prepare_bridge={boot_symbols["video_prepare_bridge"]}']
        subprocess.run([str(ROOT / ".deps/cc65/bin/ca65"), *defines, "-g", "--bin-include-dir", str(ROOT / ".deps/upernes/source/asm"), "-I", str(out), "-o", str(out / (name + ".o")),
                        str(ROOT / "snes" / (name + ".asm"))], check=True)
        subprocess.run([str(ROOT / ".deps/cc65/bin/ld65"), "-C", str(ROOT / "snes" / (name + ".cfg")),
                        "-Ln", str(out / (name + ".lbl")), "-o", str(out / (name + ".bin")),
                        str(out / (name + ".o"))], check=True)
    symbols = {}
    for line in (out / "native_runtime.lbl").read_text().splitlines():
        _, address, name = line.split()
        symbols[name.lstrip(".")] = int(address, 16)
    prg = bytearray(rom.prg)
    stubs = bytearray()
    hooks = {}
    patched = []
    seen = set()
    for trace in traces:
        manifest = json.loads((trace / "manifest.json").read_text())
        if manifest["rom_sha256"] != sha:
            raise ValueError("Trace belongs to a different ROM")
        executed = trace / "executed.jsonl"
        if hashlib.sha256(executed.read_bytes()).hexdigest() != manifest["files"][executed.name]:
            raise ValueError("Execution trace changed after capture")
        for line in executed.read_text().splitlines():
            row = json.loads(line)
            offset = row["offset"]
            if offset in seen:
                continue
            seen.add(offset)
            opcode = rom.prg[offset]
            if opcode != row["opcode"]:
                raise ValueError("Trace opcode does not match original")
            operand = int.from_bytes(rom.prg[offset + 1:offset + 3], "little")
            if opcode in (0x20, 0x4C) and operand == 0x07F8:
                key = ("ram-apu",)
                if key not in hooks:
                    hooks[key] = 0x6000 + len(stubs)
                    stubs += stub(0x8D, 0x4000, symbols["dispatch_write"], dynamic_apu=True)
                prg[offset:offset + 3] = bytes((opcode,)) + word(hooks[key])
                patched.append({"offset": offset, "pc": row["pc"], "opcode": opcode,
                                "operand": operand, "stub": hooks[key], "kind": "self-modifying RAM APU write"})
                continue
            if opcode not in WRITES and opcode not in READS:
                continue
            is_io = 0x2000 <= operand <= 0x2007 or 0x4000 <= operand <= 0x4017
            is_mapper = opcode in WRITES and operand >= 0x8000
            if not (is_io or is_mapper):
                continue
            tail = opcode == 0x8D and operand == 0x2000
            key = (opcode, operand, row["pc"] if tail else None)
            if key not in hooks:
                address = 0x6000 + len(stubs)
                entry = symbols["dispatch_write" if opcode in WRITES else "dispatch_read"]
                hooks[key] = address
                stubs += stub(opcode, operand, entry, row["pc"] + 3 if tail else None)
            prg[offset:offset + 3] = bytes((0x4C if tail else 0x20,)) + word(hooks[key])
            patched.append({"offset": offset, "pc": row["pc"], "opcode": opcode,
                            "operand": operand, "stub": hooks[key]})
    if len(stubs) > 8192:
        raise ValueError("Hardware stubs exceed available bank space")
    for pc, expected, name in ((0xFF61, b"\xa5\xf8\x29", "nmi_task_return"),
                               (0xF1D3, b"\x68\xa8\x68", "nmi_rti_return")):
        offset = 0x1E000 + pc - 0xE000
        if rom.prg[offset:offset + 3] != expected:
            raise ValueError("NMI adapter preimage mismatch")
        prg[offset:offset + 3] = b"\x4c" + word(symbols[name])
    image = bytearray(b"\xff" * 2097152)
    image[0x8000:0x10000] = (out / "native_boot.bin").read_bytes()
    runtime = (out / "native_runtime.bin").read_bytes()
    for bank in range(8):
        base = (bank + 1) * 65536
        image[base + 0x2000:base + 0x6000] = runtime
        image[base + 0x6000:base + 0x6000 + len(stubs)] = stubs
        image[base + 0x8000:base + 0xC000] = prg[bank * 16384:(bank + 1) * 16384]
        image[base + 0xC000:base + 0x10000] = prg[0x1C000:0x20000]
    image[0x90000:0xB0000] = convert_chr(rom.chr)
    image[0xB0000:0xF0000] = convert_chr(rom.chr, 4)
    image[0xF0000:0x110000] = rom.chr
    image[0xFFDC:0xFFE0] = b"\xff\xff\0\0"
    checksum = sum(image) & 0xFFFF
    struct.pack_into("<HH", image, 0xFFDC, checksum ^ 0xFFFF, checksum)
    target = out / "native-cpu.sfc"
    target.write_bytes(image)
    report = {"schema": "rcr-native-cpu-v1", "status": "experimental-menu-and-street-not-release-ready",
              "source_rom_sha256": sha, "rom_sha256": hashlib.sha256(image).hexdigest(),
              "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [Path(__file__), *sorted((ROOT / "snes").glob("native*"))]},
              "trace_manifest_sha256": [hashlib.sha256((p / "manifest.json").read_bytes()).hexdigest() for p in traces],
              "spc_sha256": deps["upernes"]["audio_sha256"],
              "palette_sha256": hashlib.sha256(rgb).hexdigest(),
              "covered_instructions": len(seen), "patches": patched, "stub_bytes": len(stubs),
              "graphics_pipeline": "prepared dirty rows, whole CHR banks and bounded per-NMI DMA",
              "limits": {"vram_bytes_per_nmi": 2048, "chr_jobs_per_nmi": 1, "row_scan_per_nmi": 32,
                         "oam_bytes_per_nmi": 544, "cgram_bytes_per_nmi": 64,
                         "prepared_rows_per_call": 2, "producer_row_scan_per_call": 128},
              "limitations": ["One selected nametable viewport; no scrolling/raster IRQ translation", "Game and audio pacing still not NES-equivalent; scene-load stalls remain",
                              "SPC game audio present but length/envelope/sweep/DMC fidelity unverified",
                              "Trace-covered hardware accesses only", "MMC3 PRG pairs assumed", "Native renderer supports 8x8 sprites only",
                              "No full-game or physical hardware validation"]}
    (out / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"rom": str(target), "patches": len(patched), "stubs": len(hooks)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=ROOT / "roms/river-city-ransom-us.nes")
    parser.add_argument("--trace", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    build(args.rom, args.trace, args.out)
