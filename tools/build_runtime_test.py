"""Assemble an asset-free SNES cartridge testing the production native adapter."""
from pathlib import Path
import struct
import subprocess

try:
    from .build_native import stub
except ImportError:
    from build_native import stub

ROOT = Path(__file__).resolve().parents[1]


def build(out, controllers=False, jump=False, nametable_mode=None, rect_dma=False,
          fill_dirty_batch=False, ring_pointer_cache=False,
          native_ring_consumer=False, oam_word_copy=False, oam_page=None, fastrom=False, word_fill=False,
          chr_read_cache=False, chr_test_high=0x10, chr_test_mode=0, bank_restore=False,
          chr_read_pair=False):
    if not 0 <= chr_test_high < 32 or chr_test_mode not in (0, 128):
        raise ValueError('Invalid CHR test page/mode')
    if oam_page is not None and not 0<=oam_page<=255:
        raise ValueError('OAM source page must be a byte')
    if nametable_mode not in (None, 0, 1):
        raise ValueError('Nametable mode must be 0 (vertical) or 1 (horizontal)')
    out.mkdir(parents=True, exist_ok=True)
    ca65, ld65 = [str(ROOT / ".deps/cc65/bin" / name) for name in ("ca65", "ld65")]
    subprocess.run([ca65, "-D", "video_prepare_bridge=32512", "-D", "audio_publish_bridge=32512",
                    *(["-D", "EXPERIMENTAL_RECT_DMA=1"] if rect_dma else []),
                    *(["-D", "EXPERIMENTAL_FILL_DIRTY_BATCH=1"] if fill_dirty_batch else []),
                    *(["-D", "EXPERIMENTAL_WORD_FILL=1"] if word_fill else []),
                    *(["-D", "EXPERIMENTAL_CHR_READ_CACHE=1"] if chr_read_cache else []),
                    *(["-D", "EXPERIMENTAL_CHR_READ_PAIR=1"] if chr_read_pair else []),
                    *(["-D", "EXPERIMENTAL_BANK_RESTORE=1"] if bank_restore else []),
                    *(["-D", "EXPERIMENTAL_RING_POINTER_CACHE=1"] if ring_pointer_cache else []),
                    *(["-D", "EXPERIMENTAL_OAM_WORD_COPY=1"] if oam_word_copy else []),
                    *(["-D", "EXPERIMENTAL_NATIVE_RING_CONSUMER=1"] if native_ring_consumer else []),
                    "-g", "-o", str(out / "runtime.o"), str(ROOT / "snes/native_runtime.asm")], check=True)
    subprocess.run([ld65, "-C", str(ROOT / "snes/native_runtime.cfg"), "-Ln", str(out / "runtime.lbl"),
                    "-o", str(out / "runtime.bin"), str(out / "runtime.o")], check=True)
    symbols = {line.split()[2].lstrip("."): int(line.split()[1], 16)
               for line in (out / "runtime.lbl").read_text().splitlines()}
    io_stub = stub(0x8D, 0x2007, symbols['dispatch_ppudata'], fast_ppudata=True)
    read_address = 24576 + len(io_stub)
    io_stub += stub(0xAD, 0x2007, symbols['dispatch_ppudata_read'], fast_ppudata=True)
    register_stubs = {}
    for name, opcode in (('io_stx_stub', 0x8E), ('io_sty_stub', 0x8C)):
        register_stubs[name] = 24576 + len(io_stub)
        io_stub += stub(opcode, 0x2007, symbols['dispatch_ppudata'], fast_ppudata=True)
    subprocess.run([ca65, '-D', f'CHR_TEST_HIGH={chr_test_high}', '-D', f'CHR_TEST_MODE={chr_test_mode}', *(['-D','FASTROM_TEST=1'] if fastrom else []), *(['-D', f'OAM_DMA_PAGE={oam_page}'] if oam_page is not None else []), *(['-D', f'NAMETABLE_TEST={nametable_mode}'] if nametable_mode is not None else []), *(["-D", "CONTROLLER_TEST=1"] if controllers or jump else []), *(["-D", "JUMP_TEST=1"] if jump else []), "-D", f'dispatch_read={symbols["dispatch_read"]}',
                    "-D", f'dispatch_write={symbols["dispatch_write"]}',
                    "-D", f'bank_switch_enter={symbols["bank_switch_enter"]}',
                    '-D', f'bulk_ppu_byte={symbols["bulk_ppu_byte"]}',
                    '-D', f'bulk_rect_bytes={symbols["bulk_rect_bytes"]}',
                    '-D', f'bulk_repeat_bytes={symbols["bulk_repeat_bytes"]}',
                    '-D', f'bulk_source_byte={symbols["bulk_source_byte"]}',
                    '-D', f'bulk_fill_pages={symbols["bulk_fill_pages"]}',
                    '-D', f'bulk_attribute_bytes={symbols["bulk_attribute_bytes"]}',
                    '-D', f'bulk_literal_bytes={symbols["bulk_literal_bytes"]}',
                    '-D', f'bulk_ring_bytes={symbols["bulk_ring_bytes"]}',
                    *(['-D', 'TEST_BANK_RESTORE=1', '-D', f'native_bank_restore={symbols["native_bank_restore"]}'] if bank_restore else []),
                    *(['-D', 'EXPERIMENTAL_NATIVE_RING_CONSUMER=1',
                       '-D', f'native_ring_consumer={symbols["native_ring_consumer"]}'] if native_ring_consumer else []),
                    "-D", 'io_write_stub=24576', '-D', f'io_read_stub={read_address}',
                    *[item for name, address in register_stubs.items() for item in ('-D', f'{name}={address}')],
                    "-o", str(out / "test.o"),
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
        for quarter in {chr_test_high & 3, (chr_test_high ^ 1) & 3}:
            image[0xF0000 + bank * 1024 + quarter*256 + 0x15] = bank ^ 0x91 ^ (quarter*0x33)
    image[0xFFDC:0xFFE0] = b"\xff\xff\0\0"
    checksum = sum(image) & 65535
    struct.pack_into("<HH", image, 0xFFDC, checksum ^ 65535, checksum)
    (out / "adapter-test.sfc").write_bytes(image)
    print(out / "adapter-test.sfc")


if __name__ == "__main__":
    build(ROOT / "build/runtime-test")
