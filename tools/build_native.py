"""Build an experimental native CPU cartridge from verified execution coverage.

This is deliberately gated as a CPU integration experiment, not a released port.
Only supplied execution coverage and explicitly pinned, previously executed
source-ROM repair sites are patched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

try:
    from .rom import Rom, convert_chr
    from .prepare_audio import prepare_engine, paired_engine, triple_engine, suppress_duty_keyons, nearest_clock_engine, triangle_dac_release_engine
except ImportError:
    from rom import Rom, convert_chr
    from prepare_audio import prepare_engine, paired_engine, triple_engine, suppress_duty_keyons, nearest_clock_engine, triangle_dac_release_engine

ROOT = Path(__file__).resolve().parents[1]
WRITES = {0x8D: "a", 0x8E: "x", 0x8C: "y", 0x9D: "a", 0x99: "a"}
READS = {0xAD: 0xAD, 0xAE: 0xAE, 0xAC: 0xAC, 0xBD: 0xAD, 0xB9: 0xAD, 0x2C: 0x2C}

# Executed by the original Present Status number printer, bank 11, BA6F..BA7B.
# Pin known code sites, never scan arbitrary ROM data for MMIO-looking bytes.
# Original input-only trace: reference-status-x11-168/executed.jsonl SHA256
# 8db89386a12cad8a129395049ad46d031fd5075a23bdd431ab1370debe0f3d0f.
STATUS_MMIO = ((0x17A6F,0xBA6F,0x2006), (0x17A75,0xBA75,0x2006),
               (0x17A7B,0xBA7B,0x2007))


def known_status_rows(prg):
    rows=[]
    for offset,pc,operand in STATUS_MMIO:
        if prg[offset:offset+3] != b'\x8d'+struct.pack('<H',operand):
            raise ValueError('Present Status MMIO preimage mismatch')
        rows.append(dict(offset=offset,pc=pc,opcode=0x8d))
    return rows


def covered_rows(traces,rom_sha,prg):
    for trace in traces:
        manifest=json.loads((trace/'manifest.json').read_text())
        if manifest['rom_sha256']!=rom_sha:
            raise ValueError('Trace belongs to a different ROM')
        executed=trace/'executed.jsonl'
        if hashlib.sha256(executed.read_bytes()).hexdigest()!=manifest['files'][executed.name]:
            raise ValueError('Execution trace changed after capture')
        yield from (json.loads(line) for line in executed.read_text().splitlines())
    # These repairs must survive builds made with an older trace set too.
    yield from known_status_rows(prg)


def direct_apu_stub(entry, generic):
    # Classify before choosing a full ABI. Non-channel addresses retain the
    # entire existing stub, including mapper's cross-bank return semantics.
    guard = bytearray.fromhex('0848adfa07c940d000adf907c9109000c915d000')
    fast = b'\x68\x28\x22' + word(entry) + b'\xc1\x60'
    guard[8] = len(guard) + len(fast) - 9
    guard[15] = len(guard) - 16
    guard[19] = len(fast)
    # The pointer is mutable sound-driver RAM: protect classification too,
    # not merely the selected write, from an intervening sound NMI.
    return b'\x9c\x00\x42' + guard + fast + b'\x68\x28' + generic


def word(value):
    return struct.pack("<H", value)


def stub(opcode, operand, entry, resume=None, dynamic_apu=False, fast_ppudata=False, experimental_raster=False, raster_rearm=None, immediate_nmi=False, software_nmi=None):
    recovery = b'' if raster_rearm is None else b'\x22'+word(raster_rearm)+b'\xc1'
    if recovery and not experimental_raster:
        raise ValueError('Raster recovery requires experimental raster mode')
    if fast_ppudata and (opcode not in (0x8D, 0x8E, 0x8C, 0xAD) or operand != 0x2007 or resume is not None or dynamic_apu):
        raise ValueError('Fast PPUDATA requires a plain STA/STX/STY/LDA $2007')
    # Disable NMI before filling the shared mailbox. Otherwise an interrupt
    # can overwrite a half-written command or a just-returned read result.
    data = bytearray((0x9C, 0x00, 0x42, 0x08, 0x48))  # STZ $4200; PHP; PHA
    if opcode in WRITES:
        if WRITES[opcode] == "x":
            data.append(0x8A)
        elif WRITES[opcode] == "y":
            data.append(0x98)
        data += b"\x8d" + word(0x1B22)
    if fast_ppudata:
        pass  # known destination; specialized entry needs no address mailbox
    elif dynamic_apu:
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
        enable = b"\x8d\x00\x42"
        if experimental_raster:
            enable = b"\x08\x48" + recovery + b"\x29\x80\x0d\xa2\x1c\x8d\x00\x42\x68\x28"
        if immediate_nmi:
            if software_nmi is None:
                raise ValueError('Immediate coroutine NMI requires native NMI entry')
            # During a rendering-off transition, emulate the NES behavior of
            # enabling NMI while VBlank is already asserted.  SNES hardware
            # has no equivalent level-triggered enable, so synthesize the
            # emulation-mode interrupt frame and enter the normal native NMI.
            # Other states retain the conservative wait-free enable below.
            immediate = (b"\x68\x48\x29\x80\xf0\x19\xad\xa0\x1c\xc9\x01\xd0\x12"
                         b"\xad\x12\x42\x10\x0d\x68\x28\xa9" + bytes([resume >> 8]) +
                         b"\x48\xa9" + bytes([resume & 255]) + b"\x48\x08\x5c" +
                         word(software_nmi) + b"\xc0")
            wait = b"\x68\x48\x29\x80\xf0\x05\xad\x12\x42\x30\xfb\x68\x28"
            return data + guard + immediate + wait + enable + b"\x4c" + word(resume)
        return data + guard + b"\x68\x48\x29\x80\xf0\x05\xad\x12\x42\x30\xfb\x68\x28" + enable + b"\x4c" + word(resume)
    # The mailbox transaction is complete. Deliver a pending edge instead of
    # waiting out VBlank; NMI entry acknowledges $4210 and the publisher now
    # budgets late entry. Both nesting/paired-bank guards still suppress enable.
    extra = b"\x0d\xa2\x1c" if experimental_raster else b""
    return (data + b"\x08\x48\xad\x0a\x1c\x0d\x83\x1c\xd0" + bytes([10+len(extra)+len(recovery)]) + recovery + b"\xad\x20\x1c\x29\x80" + extra + b"\xf0\x03"
            + b"\x8d\x00\x42\x68\x28\x60")


def build(rom_path, traces, out, experimental_fastrom=False, experimental_raster=False, experimental_paired_audio=False, raster_line=30, experimental_reset_audio=False, experimental_triple_audio=False, experimental_load_rows=None, experimental_reuse_audio=False, experimental_word_fill=False, experimental_transition_scan=False, experimental_fc60_defer=False, experimental_rect_dma=False, experimental_fc60_defer_audio=False, experimental_fc60_defer_video=False, experimental_fc60_immediate_nmi=False, experimental_fill_dirty_batch=False, experimental_attribute_lookup=False, experimental_oam_dirty_gate=False, experimental_oam_compare_unroll=False, experimental_row_stores=False, experimental_transition_prepare_defer=False, experimental_gameplay_prepare_defer=False, experimental_chr_dirty_gate=False, experimental_sprite_unroll=False, experimental_suppress_duty_keyon=False, experimental_camera_deadline=False, experimental_deferred_game_nmi=False, experimental_deferred_reset_audio=False, experimental_gameplay_rows=None, experimental_ring_pointer_cache=False, experimental_dirty_final_dma=False, experimental_transition_game_first=False, experimental_row_scan=False, experimental_native_ring_consumer=False, experimental_transition_wait_prepare=False, experimental_native_command_producer=False, experimental_native_ring_budget5=False, experimental_control_presets=False, experimental_sprite_delta=False, experimental_oam_word_copy=False, experimental_hidden_rows=None, experimental_alias_word_copy=False,
          experimental_hidden_dma=False, experimental_fused_alias_rows=False, experimental_planar_rows=False,
          experimental_hidden_row_run=False, experimental_fast_publisher=False, experimental_hidden_direct_rows=False,
          experimental_camera_nmi_reenable=False, experimental_early_deferred_audio=False,
          experimental_late_prepare_guard=False, experimental_palette_copy=False,
          experimental_pending_palette=False, experimental_pending_palette_write_head=False,
          experimental_hidden_high_cache=False, experimental_pending_palette_all_levels=False,
          experimental_hidden_sprite_defer=False, experimental_direct_apu=False,
          experimental_bank_restore=False, experimental_sound_commit=False,
          experimental_hidden_direct_pair=False, experimental_chr_read_cache=False,
          experimental_chr_read_pair=False, experimental_oam_live_half=False,
          experimental_camera_safe_publish=False, experimental_deferred_resume_line=None,
          experimental_camera_vblank_commit=False, experimental_static_camera_arm=False,
          experimental_camera_line30=False, experimental_visible_attribute_cache=False,
          experimental_visible_row_phase=False, experimental_sprite_coordinates=False,
          experimental_noise_clock=False, experimental_second_tick_prepare=False,
          experimental_sprite_position=False, experimental_joypad_poll=False,
          experimental_second_tick_deadline=False, experimental_column_fetch=False,
          experimental_main_phase_line=None, experimental_triangle_release=False,
          experimental_pulse_sweep=False, experimental_sweep_driver=False,
          experimental_retained_return_edge=False):
    if experimental_retained_return_edge and not (experimental_deferred_game_nmi
            and experimental_camera_nmi_reenable and experimental_late_prepare_guard):
        raise ValueError('Retained return edge requires deferred NMI, camera re-enable and late prepare guard')
    if experimental_sweep_driver and (not experimental_paired_audio or not experimental_reset_audio
            or experimental_triple_audio or experimental_reuse_audio or experimental_deferred_reset_audio
            or experimental_suppress_duty_keyon or experimental_pulse_sweep):
        raise ValueError('Live sweep driver requires paired fast-reset audio without competing sweep or duty patches')
    if experimental_triangle_release and (not experimental_paired_audio or not experimental_reset_audio
            or experimental_triple_audio or experimental_reuse_audio or experimental_deferred_reset_audio):
        raise ValueError('Triangle release game experiment requires paired fast-reset audio')
    if experimental_main_phase_line is not None:
        if not experimental_second_tick_prepare or not 1<=experimental_main_phase_line<=160:
            raise ValueError('Main phase requires retained second-tick preparation and an active-frame line1..160')
    if experimental_second_tick_deadline and not experimental_second_tick_prepare:
        raise ValueError('Second tick deadline requires retained second tick preparation')
    if experimental_sprite_position and experimental_sprite_coordinates:
        raise ValueError('Fused sprite position replaces the older coordinate-only experiment')
    if experimental_second_tick_prepare and (not experimental_deferred_game_nmi
            or not experimental_static_camera_arm or experimental_gameplay_prepare_defer
            or experimental_camera_deadline or experimental_visible_row_phase):
        raise ValueError('Second tick prepare requires the stationary-armed deferred scheduler without competing producer policies')
    if experimental_visible_row_phase and (not experimental_deferred_game_nmi or not experimental_fused_alias_rows
            or experimental_gameplay_prepare_defer or experimental_gameplay_rows is not None):
        raise ValueError('Visible row phase requires deferred NMI, fused rows and the default gameplay budget')
    if experimental_visible_attribute_cache and not experimental_fused_alias_rows:
        raise ValueError('Visible attribute cache requires fused rows')
    if experimental_camera_line30 and not experimental_camera_safe_publish:
        raise ValueError('Line30 camera experiment requires safe publication')
    if experimental_static_camera_arm and not (experimental_camera_safe_publish and experimental_camera_nmi_reenable):
        raise ValueError('Static camera arming requires safe publication and NMI reenable')
    if experimental_camera_vblank_commit and not experimental_camera_safe_publish:
        raise ValueError('VBlank camera commit requires safe camera publication')
    if experimental_deferred_resume_line is not None:
        if (type(experimental_deferred_resume_line) is not int or
                not 240 <= experimental_deferred_resume_line <= 250 or
                not experimental_deferred_game_nmi or experimental_raster):
            raise ValueError('Deferred resume requires integer line240..250 and the NMI-only deferred scheduler')
    if experimental_camera_safe_publish and (not experimental_deferred_game_nmi or experimental_raster):
        raise ValueError('Safe camera publication requires the NMI-only deferred scheduler')
    if experimental_oam_live_half and not experimental_sprite_delta:
        raise ValueError('Live-half OAM requires the invariant-preserving delta producer')
    if experimental_hidden_direct_pair and not experimental_hidden_high_cache:
        raise ValueError('Hidden direct pairs require hidden high cache')
    if experimental_sound_commit and not experimental_direct_apu:
        raise ValueError('Sound commit requires direct APU')
    if experimental_bank_restore and experimental_raster:
        raise ValueError('Direct bank restore currently requires the NMI-only scheduler')
    if experimental_direct_apu and experimental_raster:
        raise ValueError('Direct APU currently requires the NMI-only scheduler')
    if experimental_hidden_sprite_defer and not experimental_hidden_direct_rows:
        raise ValueError('Hidden sprite deferral requires hidden direct rows')
    if experimental_pending_palette_all_levels and not experimental_pending_palette_write_head:
        raise ValueError('All-level palette preview requires the safe write-head classifier')
    if experimental_hidden_high_cache and not experimental_hidden_direct_rows:
        raise ValueError('Hidden high cache requires hidden direct rows')
    if experimental_pending_palette_write_head and (not experimental_pending_palette or not experimental_native_ring_consumer):
        raise ValueError('Write-head palette preview requires pending palette and native ring consumer')
    if experimental_pending_palette and (not experimental_fast_publisher or not experimental_palette_copy
            or not experimental_deferred_game_nmi or experimental_transition_game_first):
        raise ValueError('Pending palette requires FastROM publisher, palette copy and deferred NMI; game-first is incompatible')
    if experimental_late_prepare_guard and not experimental_early_deferred_audio:
        raise ValueError('Late prepare guard requires early deferred audio')
    if experimental_early_deferred_audio and not experimental_deferred_game_nmi:
        raise ValueError('Early deferred audio requires deferred game NMI')
    if experimental_camera_nmi_reenable and not experimental_deferred_game_nmi:
        raise ValueError('Camera NMI re-enable requires deferred game NMI')
    if experimental_hidden_direct_rows and (not experimental_attribute_lookup or experimental_hidden_rows is None):
        raise ValueError('Hidden direct rows require attribute lookup and an explicit hidden row budget')
    if experimental_fast_publisher and not experimental_fastrom:
        raise ValueError('Fast publisher requires FastROM')
    if experimental_hidden_row_run and experimental_planar_rows:
        raise ValueError('Hidden row runs currently require interleaved staging')
    if experimental_planar_rows and experimental_fused_alias_rows:
        raise ValueError('Choose planar or interleaved fused row staging, not both')
    if experimental_fused_alias_rows and not experimental_attribute_lookup:
        raise ValueError('Fused alias rows require attribute lookup')
    if experimental_paired_audio and experimental_triple_audio:
        raise ValueError('Choose one experimental audio transport')
    if experimental_reuse_audio and (not experimental_paired_audio or experimental_reset_audio
                                     or experimental_deferred_reset_audio):
        raise ValueError('Packet reuse currently requires paired audio without reset')
    if experimental_load_rows is not None and not 1 <= experimental_load_rows <= 8:
        raise ValueError('Experimental load row budget must be 1..8')
    if experimental_gameplay_rows is not None and not 1 <= experimental_gameplay_rows <= 8:
        raise ValueError('Experimental gameplay row budget must be 1..8')
    if experimental_hidden_rows is not None:
        if not 1 <= experimental_hidden_rows <= 16 or experimental_transition_wait_prepare:
            raise ValueError('Hidden row budget must be 1..16 without wait-prepare')
    if experimental_reset_audio and not (experimental_paired_audio or experimental_triple_audio):
        raise ValueError('Reset audio requires an experimental audio transport')
    if experimental_deferred_reset_audio and (not experimental_paired_audio or experimental_triple_audio
                                              or experimental_reset_audio):
        raise ValueError('Deferred reset audio requires paired audio and no other reset mode')
    if experimental_suppress_duty_keyon and (not experimental_paired_audio or experimental_reset_audio
                                             or experimental_deferred_reset_audio):
        raise ValueError('Duty key-on suppression requires paired audio without reset synthesis')
    if experimental_camera_deadline and experimental_gameplay_prepare_defer:
        raise ValueError('Camera deadline and gameplay prepare defer are mutually exclusive experiments')
    if experimental_camera_deadline and experimental_raster:
        raise ValueError('Camera deadline and unfinished raster worker are mutually exclusive experiments')
    if experimental_deferred_game_nmi and (experimental_raster or experimental_camera_deadline or experimental_gameplay_prepare_defer):
        raise ValueError('Deferred game NMI requires the normal mutually exclusive gameplay scheduler')
    if experimental_transition_game_first and (not experimental_transition_prepare_defer or
                                               experimental_fc60_defer or experimental_fc60_defer_audio or
                                               experimental_fc60_defer_video):
        raise ValueError('Transition game-first requires transition prepare defer and immediate bridge work')
    if experimental_transition_wait_prepare and (not experimental_transition_prepare_defer or
                                                 experimental_camera_deadline or
                                                 experimental_gameplay_prepare_defer):
        raise ValueError('Transition wait-prepare requires transition prepare defer and the normal gameplay scheduler')
    if experimental_native_ring_budget5 and not experimental_native_ring_consumer:
        raise ValueError('Native ring budget 5 requires the native ring consumer')
    if not 1 <= raster_line <= 220 or (raster_line != 30 and not experimental_raster):
        raise ValueError('Raster line requires experimental raster and must be 1..220')
    original = rom_path.read_bytes()
    rom = Rom.parse(original)
    rom.require_rcr_us()
    sha = hashlib.sha256(original).hexdigest()
    deps = json.loads((ROOT / "tools/dependencies.json").read_text())
    engine = ROOT / ".deps/upernes" / deps["upernes"]["audio_path"]
    if hashlib.sha256(engine.read_bytes()).hexdigest() != deps["upernes"]["audio_sha256"]:
        raise ValueError("Unexpected SPC engine")
    out.mkdir(parents=True, exist_ok=False)
    patched_engine = (triple_engine if experimental_triple_audio else
                      paired_engine if experimental_paired_audio else
                      prepare_engine)(engine.read_bytes())
    if experimental_reuse_audio:
        patched_engine = paired_engine(engine.read_bytes(), reuse_packet=True)
    if experimental_reset_audio:
        patched_engine = (triple_engine(engine.read_bytes(), reset_notes=True, fast_reset=True)
                          if experimental_triple_audio else
                          paired_engine(engine.read_bytes(), reset_notes=True, fast_reset=True))
    if experimental_deferred_reset_audio:
        patched_engine = paired_engine(engine.read_bytes(), reset_notes=True, deferred_reset=True)
    if experimental_suppress_duty_keyon:
        patched_engine = suppress_duty_keyons(patched_engine)
    if experimental_noise_clock:
        patched_engine = nearest_clock_engine(patched_engine)
    if experimental_pulse_sweep:
        try:
            from .correct_pulse_sweep import correct
        except ImportError:
            from correct_pulse_sweep import correct
        patched_engine = correct(patched_engine)
    if experimental_triangle_release:
        patched_engine = triangle_dac_release_engine(patched_engine, attack=True, in_place=True)
    sweep_driver_layout = None
    if experimental_sweep_driver:
        try:
            from .build_sweep_driver import build as build_sweep_driver
        except ImportError:
            from tools.build_sweep_driver import build as build_sweep_driver
        patched_engine, sweep_driver_layout = build_sweep_driver(patched_engine)
    (out / 'Memblers_2a03.bin').write_bytes(patched_engine)
    rgb = Path("/usr/share/fceux/palettes/FCEUX.pal").read_bytes()
    colors = [(rgb[i] >> 3) | ((rgb[i + 1] >> 3) << 5) | ((rgb[i + 2] >> 3) << 10) for i in range(0, 192, 3)]
    (out / "native_palette.inc").write_text(".word " + ",".join(f"${n:04X}" for n in colors) + "\n")
    for name in ("native_boot", "native_runtime"):
        defines = []
        if experimental_retained_return_edge:
            defines += ['-D', 'EXPERIMENTAL_RETAINED_RETURN_EDGE=1']
        if experimental_sweep_driver:
            defines += ['-D', 'EXPERIMENTAL_SWEEP_EVENTS=1',
                        '-D', f'SWEEP_DRIVER_BYTES={len(patched_engine)}']
        if name == 'native_boot' and experimental_triangle_release:
            defines += ['-D', 'EXPERIMENTAL_TRIANGLE_RELEASE=1']
        if name == 'native_runtime' and experimental_sprite_coordinates:
            defines += ['-D', 'EXPERIMENTAL_SPRITE_COORDINATES=1']
        if name == 'native_runtime' and experimental_sprite_position:
            defines += ['-D', 'EXPERIMENTAL_SPRITE_POSITION=1']
        if name == 'native_runtime' and experimental_joypad_poll:
            defines += ['-D', 'EXPERIMENTAL_JOYPAD_POLL=1']
        if name == 'native_runtime' and experimental_column_fetch:
            defines += ['-D', 'EXPERIMENTAL_COLUMN_FETCH=1']
        if name == 'native_runtime' and experimental_main_phase_line is not None:
            defines += ['-D', f'MAIN_PHASE_LINE={experimental_main_phase_line}']
        if name == 'native_runtime' and experimental_sound_commit:
            defines += ['-D', 'EXPERIMENTAL_SOUND_COMMIT=1']
        if name == 'native_runtime' and experimental_chr_read_cache:
            defines += ['-D', 'EXPERIMENTAL_CHR_READ_CACHE=1']
        if name == 'native_runtime' and experimental_chr_read_pair:
            defines += ['-D', 'EXPERIMENTAL_CHR_READ_PAIR=1']
        if name == 'native_runtime' and experimental_bank_restore:
            defines += ['-D', 'EXPERIMENTAL_BANK_RESTORE=1']
        if name == 'native_runtime' and experimental_direct_apu:
            defines += ['-D', 'EXPERIMENTAL_DIRECT_APU=1']
        if experimental_early_deferred_audio:
            defines += ['-D', 'EXPERIMENTAL_EARLY_DEFERRED_AUDIO=1']
        if name == 'native_runtime' and experimental_late_prepare_guard:
            defines += ['-D', 'EXPERIMENTAL_LATE_PREPARE_GUARD=1']
        if experimental_control_presets:
            defines += ['-D', 'EXPERIMENTAL_CONTROL_PRESETS=1']
        if name == 'native_runtime' and experimental_palette_copy:
            defines += ['-D', 'EXPERIMENTAL_PALETTE_COPY=1']
        if name == 'native_boot' and experimental_pending_palette:
            defines += ['-D', 'EXPERIMENTAL_PENDING_PALETTE=1']
        if name == 'native_boot' and experimental_fastrom:
            defines += ['-D', 'EXPERIMENTAL_FASTROM=1']
        if name == 'native_boot' and experimental_fast_publisher:
            defines += ['-D', 'EXPERIMENTAL_FAST_PUBLISHER=1']
        if name == 'native_boot' and experimental_camera_vblank_commit:
            defines += ['-D', 'EXPERIMENTAL_CAMERA_VBLANK_COMMIT=1']
        if name == 'native_boot' and experimental_deferred_resume_line is not None:
            defines += ['-D', f'DEFERRED_RESUME_LINE={experimental_deferred_resume_line}']
        if name == 'native_boot' and experimental_oam_live_half:
            defines += ['-D', 'EXPERIMENTAL_OAM_LIVE_HALF=1']
        if name == 'native_boot' and experimental_hidden_direct_rows:
            defines += ['-D', 'EXPERIMENTAL_HIDDEN_DIRECT_ROWS=1']
        if name == 'native_boot' and experimental_hidden_high_cache:
            defines += ['-D', 'EXPERIMENTAL_HIDDEN_HIGH_CACHE=1']
        if name == 'native_boot' and experimental_visible_attribute_cache:
            defines += ['-D', 'EXPERIMENTAL_VISIBLE_ATTRIBUTE_CACHE=1']
        if name == 'native_boot' and experimental_visible_row_phase:
            defines += ['-D', 'EXPERIMENTAL_VISIBLE_ROW_PHASE=1']
        if name == 'native_boot' and experimental_hidden_sprite_defer:
            defines += ['-D', 'EXPERIMENTAL_HIDDEN_SPRITE_DEFER=1']
        if name == 'native_boot' and experimental_load_rows is not None:
            defines += ['-D', f'LOAD_ROW_BUDGET={experimental_load_rows}']
        if name == 'native_boot' and experimental_gameplay_rows is not None:
            defines += ['-D', f'GAMEPLAY_ROW_BUDGET={experimental_gameplay_rows}']
        if name == 'native_boot' and experimental_hidden_rows is not None:
            defines += ['-D', f'HIDDEN_ROW_BUDGET={experimental_hidden_rows}']
        if name == 'native_boot' and experimental_alias_word_copy:
            defines += ['-D', 'EXPERIMENTAL_ALIAS_WORD_COPY=1']
        if name == 'native_boot' and experimental_hidden_dma:
            defines += ['-D', 'EXPERIMENTAL_HIDDEN_DMA=1']
        if name == 'native_boot' and experimental_fused_alias_rows:
            defines += ['-D', 'EXPERIMENTAL_FUSED_ALIAS_ROWS=1']
        if name == 'native_boot' and experimental_planar_rows:
            defines += ['-D', 'EXPERIMENTAL_PLANAR_ROWS=1']
        if name == 'native_boot' and experimental_hidden_row_run:
            defines += ['-D', 'EXPERIMENTAL_HIDDEN_ROW_RUN=1']
        if name == 'native_boot' and experimental_hidden_direct_pair:
            defines += ['-D', 'EXPERIMENTAL_HIDDEN_DIRECT_PAIR=1']
        if name == 'native_boot' and experimental_transition_scan:
            defines += ['-D', 'EXPERIMENTAL_TRANSITION_SCAN=1']
        if name == 'native_boot' and experimental_attribute_lookup:
            defines += ['-D', 'EXPERIMENTAL_ATTRIBUTE_LOOKUP=1']
        if name == 'native_boot' and experimental_transition_prepare_defer:
            defines += ['-D', 'EXPERIMENTAL_TRANSITION_PREPARE_DEFER=1']
        if name == 'native_boot' and experimental_gameplay_prepare_defer:
            defines += ['-D', 'EXPERIMENTAL_GAMEPLAY_PREPARE_DEFER=1']
        if name == 'native_boot' and experimental_deferred_game_nmi:
            defines += ['-D', 'EXPERIMENTAL_DEFERRED_GAME_NMI=1']
        if name == 'native_boot' and experimental_chr_dirty_gate:
            defines += ['-D', 'EXPERIMENTAL_CHR_DIRTY_GATE=1']
        if name == 'native_boot' and experimental_sprite_unroll:
            defines += ['-D', 'EXPERIMENTAL_SPRITE_UNROLL=1']
        if name == 'native_boot' and experimental_sprite_delta:
            defines += ['-D', 'EXPERIMENTAL_SPRITE_DELTA=1']
        if name == 'native_boot' and experimental_oam_dirty_gate:
            defines += ['-D', 'EXPERIMENTAL_OAM_DIRTY_GATE=1']
        if name == 'native_boot' and experimental_oam_compare_unroll:
            defines += ['-D', 'EXPERIMENTAL_OAM_COMPARE_UNROLL=1']
        if name == 'native_boot' and experimental_row_stores:
            defines += ['-D', 'EXPERIMENTAL_ROW_STORES=1']
        if name == 'native_boot' and experimental_dirty_final_dma:
            defines += ['-D', 'EXPERIMENTAL_DIRTY_FINAL_DMA=1']
        if name == 'native_boot' and experimental_transition_game_first:
            defines += ['-D', 'EXPERIMENTAL_TRANSITION_GAME_FIRST=1']
        if name == 'native_boot' and experimental_row_scan:
            defines += ['-D', 'EXPERIMENTAL_ROW_SCAN=1']
        if name == 'native_boot' and experimental_transition_wait_prepare:
            defines += ['-D', 'EXPERIMENTAL_TRANSITION_WAIT_PREPARE=1']
        if name == "native_runtime":
            if experimental_static_camera_arm:
                defines += ['-D', 'EXPERIMENTAL_STATIC_CAMERA_ARM=1']
            if experimental_camera_line30:
                defines += ['-D', 'EXPERIMENTAL_CAMERA_LINE30=1']
            if experimental_camera_nmi_reenable:
                defines += ['-D', 'EXPERIMENTAL_CAMERA_NMI_REENABLE=1']
            if experimental_camera_safe_publish:
                defines += ['-D', 'EXPERIMENTAL_CAMERA_SAFE_PUBLISH=1']
            boot_symbols = {line.split()[2].lstrip("."): int(line.split()[1], 16)
                            for line in (out / "native_boot.lbl").read_text().splitlines()}
            defines += ["-D", f'video_prepare_bridge={boot_symbols["video_prepare_bridge"]}',
                        "-D", f'audio_publish_bridge={boot_symbols["audio_publish_bridge"]}']
            if experimental_transition_game_first:
                defines += ['-D', 'EXPERIMENTAL_TRANSITION_GAME_FIRST=1',
                            '-D', f'video_publish_bridge={boot_symbols["video_publish_bridge"]}']
            if experimental_word_fill:
                defines += ['-D', 'EXPERIMENTAL_WORD_FILL=1']
            if experimental_fc60_defer or experimental_fc60_defer_audio or experimental_fc60_defer_video:
                defines += ['-D', 'EXPERIMENTAL_FC60_DEFER=1']
            if experimental_fc60_defer or experimental_fc60_defer_audio:
                defines += ['-D', 'EXPERIMENTAL_FC60_DEFER_AUDIO=1']
            if experimental_fc60_defer or experimental_fc60_defer_video:
                defines += ['-D', 'EXPERIMENTAL_FC60_DEFER_VIDEO=1']
            if experimental_rect_dma:
                defines += ['-D', 'EXPERIMENTAL_RECT_DMA=1']
            if experimental_fill_dirty_batch:
                defines += ['-D', 'EXPERIMENTAL_FILL_DIRTY_BATCH=1']
            if experimental_oam_dirty_gate:
                defines += ['-D', 'EXPERIMENTAL_OAM_DIRTY_GATE=1']
            if experimental_oam_word_copy:
                defines += ['-D', 'EXPERIMENTAL_OAM_WORD_COPY=1']
            if experimental_transition_prepare_defer:
                defines += ['-D', 'EXPERIMENTAL_TRANSITION_PREPARE_DEFER=1']
            if experimental_gameplay_prepare_defer:
                defines += ['-D', 'EXPERIMENTAL_GAMEPLAY_PREPARE_DEFER=1']
            if experimental_second_tick_prepare:
                defines += ['-D', 'EXPERIMENTAL_SECOND_TICK_PREPARE=1']
            if experimental_second_tick_deadline:
                defines += ['-D', 'EXPERIMENTAL_SECOND_TICK_DEADLINE=1']
            if experimental_camera_deadline:
                defines += ['-D', 'EXPERIMENTAL_CAMERA_DEADLINE=1']
            if experimental_deferred_game_nmi:
                defines += ['-D', 'EXPERIMENTAL_DEFERRED_GAME_NMI=1']
            if experimental_chr_dirty_gate:
                defines += ['-D', 'EXPERIMENTAL_CHR_DIRTY_GATE=1']
            if experimental_ring_pointer_cache:
                defines += ['-D', 'EXPERIMENTAL_RING_POINTER_CACHE=1']
            if experimental_native_ring_consumer:
                defines += ['-D', 'EXPERIMENTAL_NATIVE_RING_CONSUMER=1']
            if experimental_transition_wait_prepare:
                defines += ['-D', 'EXPERIMENTAL_TRANSITION_WAIT_PREPARE=1']
            if experimental_native_command_producer:
                defines += ['-D', 'EXPERIMENTAL_NATIVE_COMMAND_PRODUCER=1']
            if experimental_native_ring_budget5:
                defines += ['-D', 'EXPERIMENTAL_NATIVE_RING_BUDGET5=1']
        if experimental_paired_audio and name == 'native_boot':
            defines += ['-D', 'AUDIO_PAIR=1']
            if experimental_reuse_audio:
                defines += ['-D', 'AUDIO_REUSE=1']
            if experimental_reset_audio:
                defines += ['-D', 'AUDIO_FAST_RESET=1']
            if experimental_deferred_reset_audio:
                defines += ['-D', 'AUDIO_DEFERRED_RESET=1']
        if experimental_triple_audio and name == 'native_boot':
            defines += ['-D', 'AUDIO_TRIPLE=1']
            if experimental_reset_audio:
                defines += ['-D', 'AUDIO_FAST_RESET=1']
        if experimental_raster:
            defines += ['-D', 'EXPERIMENTAL_RASTER=1']
            defines += ['-D', f'RASTER_LINE={raster_line}']
            if name == 'native_runtime':
                defines += ['-D', 'RASTER_RECOVERY=1']
        subprocess.run([str(ROOT / ".deps/cc65/bin/ca65"), *defines, "-g", "--bin-include-dir", str(out), "-I", str(out), "-o", str(out / (name + ".o")),
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
    for row in covered_rows(traces, sha, rom.prg):
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
                if experimental_direct_apu:
                    stubs += direct_apu_stub(symbols['direct_dynamic_apu'],
                        stub(0x8D, 0x4000, symbols['dispatch_write'], dynamic_apu=True))
                else:
                    stubs += stub(0x8D, 0x4000, symbols["dispatch_write"], dynamic_apu=True, experimental_raster=experimental_raster,
                                  raster_rearm=symbols.get('raster_rearm'))
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
            # Register-store specialization is covered by the adapter
            # fixture, but did not improve the measured game replay.
            fast_ppudata = opcode in (0x8D, 0xAD) and operand == 0x2007
            if fast_ppudata:
                entry = symbols['dispatch_ppudata' if opcode in WRITES else 'dispatch_ppudata_read']
            hooks[key] = address
            stubs += stub(opcode, operand, entry, row["pc"] + 3 if tail else None,
                          fast_ppudata=fast_ppudata, experimental_raster=experimental_raster,
                          raster_rearm=symbols.get('raster_rearm'),
                          immediate_nmi=experimental_fc60_immediate_nmi and row['pc'] == 0xFC70,
                          software_nmi=boot_symbols.get('nmi'))
        prg[offset:offset + 3] = bytes((0x4C if tail else 0x20,)) + word(hooks[key])
        patched.append({"offset": offset, "pc": row["pc"], "opcode": opcode,
                        "operand": operand, "stub": hooks[key]})
    if len(stubs) > 8192:
        raise ValueError("Hardware stubs exceed available bank space")
    bulk_offset = 0x1C90C
    if experimental_palette_copy:
        palette_preimage=bytes.fromhex('bd10018d0720e8e02090f5')
        if rom.prg[0x1E477:0x1E482]!=palette_preimage:
            raise ValueError('Palette-copy loop preimage mismatch')
        prg[0x1E477:0x1E47A]=b'\x4c'+word(symbols['palette_copy_loop'])
    bulk_preimage = bytes.fromhex('a52d8d0620a52c8d0620a51b8d072018a52c6901852ca52d6900852d60')
    if rom.prg[bulk_offset:bulk_offset + len(bulk_preimage)] != bulk_preimage:
        raise ValueError('Bulk PPU byte helper preimage mismatch')
    prg[bulk_offset:bulk_offset + 3] = b'\x4c' + word(symbols['bulk_ppu_byte'])
    rect_offset=0x1C88F
    rect_preimage=bytes.fromhex('a61d200cc9cad0fac61cd0f4')
    if rom.prg[rect_offset:rect_offset+len(rect_preimage)]!=rect_preimage:
        raise ValueError('Rectangular decompressor outer-loop preimage mismatch')
    prg[rect_offset:rect_offset+3]=b'\x4c'+word(symbols['bulk_rect_loop'])
    repeat_offset=0x1C861
    repeat_preimage=bytes.fromhex('200cc9cad0fa')
    if rom.prg[repeat_offset:repeat_offset+len(repeat_preimage)]!=repeat_preimage:
        raise ValueError('Repeated-byte loop preimage mismatch')
    prg[repeat_offset:repeat_offset+3]=b'\x4c'+word(symbols['bulk_repeat_loop'])
    literal_preimage = bytes.fromhex('20dbc8200cc9cad0f7')
    if rom.prg[0x1C872:0x1C87B] != literal_preimage:
        raise ValueError('Literal command loop preimage mismatch')
    prg[0x1C872:0x1C875] = b'\x4c' + word(symbols['bulk_literal_loop'])
    if experimental_fc60_defer or experimental_fc60_defer_audio or experimental_fc60_defer_video:
        fc60_offset = 0x1FC60
        fc60_preimage = bytes.fromhex('48ad0001')
        if rom.prg[fc60_offset:fc60_offset + len(fc60_preimage)] != fc60_preimage:
            raise ValueError('FC60 coroutine preimage mismatch')
        prg[fc60_offset:fc60_offset + 4] = b'\x4c' + word(symbols['fc60_deferred_work']) + b'\xea'
    if experimental_gameplay_prepare_defer or experimental_camera_deadline:
        camera_offset = 0x1E2AF
        camera_preimage = bytes.fromhex('e53b85f660')
        if rom.prg[camera_offset:camera_offset + len(camera_preimage)] != camera_preimage:
            raise ValueError('Gameplay camera tail preimage mismatch')
        camera_entry = ('camera_deadline_exit' if experimental_camera_deadline
                        else 'camera_prepare_exit')
        prg[camera_offset:camera_offset + 5] = b'\x4c' + word(symbols[camera_entry]) + b'\xea\xea'
    if experimental_camera_deadline:
        poll_offset = 0x1F2C9
        poll_preimage = bytes.fromhex('ad0b01c90290f9')
        if rom.prg[poll_offset:poll_offset + len(poll_preimage)] != poll_preimage:
            raise ValueError('Gameplay end-of-iteration poll preimage mismatch')
        prg[poll_offset:poll_offset + 3] = b'\x20' + word(symbols['camera_deadline_poll'])
    if experimental_deferred_game_nmi:
        iteration_offset = 0x1F27D
        iteration_preimage = bytes.fromhex('a9008d0b01')
        if rom.prg[iteration_offset:iteration_offset + len(iteration_preimage)] != iteration_preimage:
            raise ValueError('Gameplay iteration-start preimage mismatch')
        iteration_entry = symbols['gameplay_iteration_start']
        if experimental_main_phase_line is not None:
            iteration_entry = symbols['gameplay_phase_start']
        prg[iteration_offset:iteration_offset + 5] = b'\x4c' + word(iteration_entry) + b'\xea\xea'
        camera_offset = 0x1E2AF
        camera_preimage = bytes.fromhex('e53b85f660')
        if rom.prg[camera_offset:camera_offset + len(camera_preimage)] != camera_preimage:
            raise ValueError('Deferred-game-NMI camera tail preimage mismatch')
        prg[camera_offset:camera_offset + 5] = b'\x4c' + word(symbols['camera_deferred_nmi_exit']) + b'\xea\xea'
        pause_branch_offset = 0x1F289
        pause_branch_preimage = bytes.fromhex('d029')
        if rom.prg[pause_branch_offset:pause_branch_offset + len(pause_branch_preimage)] != pause_branch_preimage:
            raise ValueError('Deferred-game-NMI pause branch preimage mismatch')
        # BNE F2E7, the nearby exit gateway replaced below.  This changes only
        # the taken pause path; F28B..F2B4 remains the exact original fast path.
        prg[pause_branch_offset:pause_branch_offset + 2] = bytes.fromhex('d05c')
        pause_gateway_offset = 0x1F2E7
        pause_gateway_preimage = bytes.fromhex('2050fc4c76ff')
        if rom.prg[pause_gateway_offset:pause_gateway_offset + len(pause_gateway_preimage)] != pause_gateway_preimage:
            raise ValueError('Deferred-game-NMI pause gateway preimage mismatch')
        prg[pause_gateway_offset:pause_gateway_offset + 3] = b'\x4c' + word(symbols['deferred_game_nmi_pause_gateway'])
    if experimental_transition_wait_prepare:
        wait_offset = 0x1F2BA
        wait_preimage = bytes.fromhex('eaeaea')
        if rom.prg[wait_offset:wait_offset + len(wait_preimage)] != wait_preimage:
            raise ValueError('Transition wait-prepare poll preimage mismatch')
        prg[wait_offset:wait_offset + 3] = b'\x20' + word(symbols['transition_wait_prepare_poll'])
    source_offset = 0x1C8DB
    source_preimage = bytes.fromhex('a52bc980b022a51a18652a852ea52b6900852fa52f8d0620a52e8d0620ad0720ad0720851be61a60a41ab12a851be61a60')
    if rom.prg[source_offset:source_offset + len(source_preimage)] != source_preimage:
        raise ValueError('Bulk source helper preimage mismatch')
    prg[source_offset:source_offset + 3] = b'\x4c' + word(symbols['bulk_source_byte'])
    fill_offset = 0x1FCB2
    fill_preimage = bytes.fromhex('850486058406ad0220a5f829fb8d002085f8a5048d0620a0008c0620a204c920b002a606a000a5058d072088d0facad0f7')
    if rom.prg[fill_offset:fill_offset + len(fill_preimage)] != fill_preimage:
        raise ValueError('Aligned page fill setup/loop preimage mismatch')
    prg[0x1FCD6:0x1FCD9] = b'\x4c' + word(symbols['bulk_fill_loop'])
    attribute_preimage = bytes.fromhex('8c0720cad0fa')
    if rom.prg[0x1FCF7:0x1FCFD] != attribute_preimage:
        raise ValueError('Attribute fill loop preimage mismatch')
    prg[0x1FCF7:0x1FCFA] = b'\x4c' + word(symbols['bulk_attribute_loop'])
    ring_preimage = bytes.fromhex('bd45058d0720e88a293faa88d0f2')
    if rom.prg[0x1C575:0x1C575 + len(ring_preimage)] != ring_preimage:
        raise ValueError('Graphics ring loop preimage mismatch')
    prg[0x1C575:0x1C578] = b'\x4c' + word(symbols['bulk_ring_loop'])
    if experimental_native_ring_consumer:
        consumer_offset = 0x1C50B
        consumer_preimage = bytes.fromhex('a50448a001ad3e002902d002a0048404')
        if rom.prg[consumer_offset:consumer_offset + len(consumer_preimage)] != consumer_preimage:
            raise ValueError('Graphics command consumer preimage mismatch')
        prg[consumer_offset:consumer_offset + 3] = b'\x4c' + word(symbols['native_ring_consumer'])
    if experimental_native_command_producer:
        producer_offset = 0x1CF04
        producer_preimage = bytes.fromhex('c900f02ec90bd005a99f4c36cfc93ad008a90048a9ba4c39cfc970b008a90048a9ba4c39cfc9b0b00918695048a9ae4c39cf48a90048aeb706a52b9d450520fdcaa52a9d450520fdcaa9049d450520fdcaa9029d450520fdca689d450520fdca689d450520fdca8eb70660')
        if rom.prg[producer_offset:producer_offset + len(producer_preimage)] != producer_preimage:
            raise ValueError('Native command producer preimage mismatch')
        prg[producer_offset:producer_offset + 3] = b'\x4c' + word(symbols['native_command_producer'])
    if experimental_sound_commit:
        offset = 0x14735
        expected = bytes.fromhex('99d607e004b00abd4c07d0118cf907f00698290f8df907b9d6074cf80760')
        if rom.prg[offset:offset+len(expected)] != expected:
            raise ValueError('Sound commit preimage mismatch')
        prg[offset:offset+3] = b'\x4c' + word(symbols['native_sound_commit'])
    if experimental_sprite_coordinates:
        offset = 0x1EF11
        expected = bytes.fromhex('a200b50818750e9508b50f75099509e8e8e00490ed')
        if prg[offset:offset+len(expected)] != expected:
            raise ValueError('Unexpected original sprite coordinate loop')
        prg[offset:offset+3] = b'\x4c' + word(symbols['native_sprite_coordinates'])
    if experimental_sprite_position:
        offset = 0x1EEEE
        expected = bytes.fromhex('a9008509850ba51a0aa8b12ea604f00249ff850829ff1002c609c8b12e850a1002c60ba200b50818750e9508b50f75099509e8e8e00490ed')
        if prg[offset:offset+len(expected)] != expected:
            raise ValueError('Sprite position preimage mismatch')
        prg[offset:offset+4] = b'\x4c' + word(symbols['native_sprite_position']) + b'\xea'
    if experimental_column_fetch:
        offset = 0x1C2C3
        expected = bytes.fromhex('a421b11a851ec8b11a851fa420b11e9d4505e82006c5e621e621a521c93090e0')
        if prg[offset:offset+len(expected)] != expected:
            raise ValueError('Column fetch preimage mismatch')
        prg[offset:offset+3] = b'\x4c' + word(symbols['native_column_fetch'])
    if experimental_joypad_poll:
        offset = 0x1FD8E
        expected = bytes.fromhex('ad16404a26ee4a2604ad17404a26ef4a2605cad0eb')
        if rom.prg[offset:offset+len(expected)] != expected:
            raise ValueError('Joypad polling loop preimage mismatch')
        if prg[offset] != 0x20 or prg[offset+9] != 0x20:
            raise ValueError('Joypad reads must already have translated stubs')
        prg[offset:offset+3] = b'\x4c' + word(symbols['native_joypad_poll'])
    if experimental_bank_restore:
        offset = 0x1FF29
        expected = bytes.fromhex('a90085ffa90685ff8d0080a5fc8d0180a90785ff8d0080a5fd8d0180a90085ffa5fb8d008060')
        if rom.prg[offset:offset+len(expected)] != expected:
            raise ValueError('Direct bank restore preimage mismatch')
        prg[offset:offset+3] = b'\x4c' + word(symbols['native_bank_restore'])
    for pc, expected, name in ((0xFF61, b"\xa5\xf8\x29", "nmi_task_return"),
                               (0xF1D3, b"\x68\xa8\x68", "nmi_rti_return"),
                               (0xFED1, b"\x48\x8a\x48", "bank_switch_enter"),
                               (0xFEFB, b"\xcd\xff\xbf", "bank_switch_exit")):
        offset = 0x1E000 + pc - 0xE000
        if rom.prg[offset:offset + 3] != expected:
            raise ValueError("NMI adapter preimage mismatch")
        prg[offset:offset + 3] = b"\x4c" + word(symbols[name])
    image = bytearray(b"\xff" * 2097152)
    if experimental_pending_palette:
        subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g','-D',f'native_palette={boot_symbols["native_palette"]}',
            *(['-D','EXPERIMENTAL_PENDING_PALETTE_WRITE_HEAD=1'] if experimental_pending_palette_write_head else []),
            *(['-D','EXPERIMENTAL_PENDING_PALETTE_ALL_LEVELS=1'] if experimental_pending_palette_all_levels else []),
            '-o',str(out/'pending_palette.o'),str(ROOT/'snes/pending_palette.asm')],check=True)
        subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/pending_palette.cfg'),
            '-Ln',str(out/'pending_palette.lbl'),'-o',str(out/'pending_palette.bin'),
            str(out/'pending_palette.o')],check=True)
        image[0x7000:0x8000]=(out/'pending_palette.bin').read_bytes()
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
    if experimental_sweep_driver:
        if len(patched_engine)>0x10000 or image[0x120000:0x130000]!=b'\xff'*0x10000:
            raise ValueError('Expanded audio engine needs an unused D2 bank')
        image[0x120000:0x120000+len(patched_engine)]=patched_engine
    image[0xFFDC:0xFFE0] = b"\xff\xff\0\0"
    checksum = sum(image) & 0xFFFF
    struct.pack_into("<HH", image, 0xFFDC, checksum ^ 0xFFFF, checksum)
    target = out / "native-cpu.sfc"
    target.write_bytes(image)
    report = {"schema": "rcr-native-cpu-v1", "status": "experimental-menu-and-street-not-release-ready",
              "experimental_fastrom": experimental_fastrom,
              "experimental_raster": experimental_raster,
              "experimental_paired_audio": experimental_paired_audio,
              "experimental_triple_audio": experimental_triple_audio,
              "experimental_oam_live_half": experimental_oam_live_half,
              "experimental_camera_safe_publish": experimental_camera_safe_publish,
              "experimental_camera_vblank_commit": experimental_camera_vblank_commit,
              "experimental_static_camera_arm": experimental_static_camera_arm,
              "experimental_camera_line30": experimental_camera_line30,
              "experimental_visible_attribute_cache": experimental_visible_attribute_cache,
              "experimental_visible_row_phase": experimental_visible_row_phase,
              "experimental_sprite_coordinates": experimental_sprite_coordinates,
              "experimental_sprite_position": experimental_sprite_position,
              "experimental_joypad_poll": experimental_joypad_poll,
              "joypad_poll_source_sha256": hashlib.sha256((ROOT/'snes/joypad_poll.inc').read_bytes()).hexdigest() if experimental_joypad_poll else None,
              "sprite_position_source_sha256": hashlib.sha256((ROOT/'snes/sprite_position.inc').read_bytes()).hexdigest() if experimental_sprite_position else None,
              "sprite_coordinates_source_sha256": hashlib.sha256((ROOT/'snes/sprite_coordinates.inc').read_bytes()).hexdigest(),
              "visible_row_phase_policy": ({"stable_tick1": 4, "stable_tick2": 0,
                  "other_gameplay": 2, "audio_palette_sprites_chr": "every original NMI"}
                  if experimental_visible_row_phase else None),
              "experimental_load_rows": experimental_load_rows,
              "experimental_gameplay_rows": experimental_gameplay_rows,
              "experimental_hidden_rows": experimental_hidden_rows,
              "experimental_alias_word_copy": experimental_alias_word_copy,
              "experimental_hidden_dma": experimental_hidden_dma,
              "experimental_fused_alias_rows": experimental_fused_alias_rows,
              "experimental_planar_rows": experimental_planar_rows,
              "experimental_hidden_row_run": experimental_hidden_row_run,
              "experimental_fast_publisher": experimental_fast_publisher,
              "experimental_hidden_direct_rows": experimental_hidden_direct_rows,
              "experimental_hidden_high_cache": experimental_hidden_high_cache,
              "experimental_hidden_direct_pair": experimental_hidden_direct_pair,
              "experimental_chr_read_cache": experimental_chr_read_cache,
              "experimental_chr_read_pair": experimental_chr_read_pair,
              "experimental_hidden_sprite_defer": experimental_hidden_sprite_defer,
              "experimental_direct_apu": experimental_direct_apu,
              "experimental_bank_restore": experimental_bank_restore,
              "experimental_sound_commit": experimental_sound_commit,
              "experimental_camera_nmi_reenable": experimental_camera_nmi_reenable,
              "experimental_early_deferred_audio": experimental_early_deferred_audio,
              "experimental_late_prepare_guard": experimental_late_prepare_guard,
              "experimental_deferred_resume_line": experimental_deferred_resume_line,
              "experimental_palette_copy": experimental_palette_copy,
              "experimental_pending_palette": experimental_pending_palette,
              "experimental_pending_palette_write_head": experimental_pending_palette_write_head,
              "experimental_pending_palette_all_levels": experimental_pending_palette_all_levels,
              "experimental_ring_pointer_cache": experimental_ring_pointer_cache,
              "experimental_dirty_final_dma": experimental_dirty_final_dma,
              "experimental_control_presets": experimental_control_presets,
              "experimental_transition_game_first": experimental_transition_game_first,
              "experimental_row_scan": experimental_row_scan,
              "experimental_native_ring_consumer": experimental_native_ring_consumer,
              "experimental_transition_wait_prepare": experimental_transition_wait_prepare,
              "experimental_native_command_producer": experimental_native_command_producer,
              "experimental_native_ring_budget5": experimental_native_ring_budget5,
              "experimental_reuse_audio": experimental_reuse_audio,
              "experimental_word_fill": experimental_word_fill,
              "experimental_transition_scan": experimental_transition_scan,
              "experimental_fc60_defer": experimental_fc60_defer,
              "experimental_fc60_defer_audio": experimental_fc60_defer_audio,
              "experimental_fc60_defer_video": experimental_fc60_defer_video,
              "experimental_fc60_immediate_nmi": experimental_fc60_immediate_nmi,
              "experimental_rect_dma": experimental_rect_dma,
              "experimental_fill_dirty_batch": experimental_fill_dirty_batch,
              "experimental_attribute_lookup": experimental_attribute_lookup,
              "experimental_oam_dirty_gate": experimental_oam_dirty_gate,
              "experimental_oam_compare_unroll": experimental_oam_compare_unroll,
              "experimental_row_stores": experimental_row_stores,
              "experimental_transition_prepare_defer": experimental_transition_prepare_defer,
              "experimental_gameplay_prepare_defer": experimental_gameplay_prepare_defer,
              "experimental_chr_dirty_gate": experimental_chr_dirty_gate,
              "experimental_sprite_unroll": experimental_sprite_unroll,
              "experimental_sprite_delta": experimental_sprite_delta,
              "experimental_oam_word_copy": experimental_oam_word_copy,
              "experimental_suppress_duty_keyon": experimental_suppress_duty_keyon,
              "experimental_camera_deadline": experimental_camera_deadline,
              "experimental_deferred_game_nmi": experimental_deferred_game_nmi,
              "experimental_deferred_reset_audio": experimental_deferred_reset_audio,
              "experimental_reset_audio": experimental_reset_audio,
              "experimental_raster_line": raster_line if experimental_raster else None,
              "source_rom_sha256": sha, "rom_sha256": hashlib.sha256(image).hexdigest(),
              "known_status_mmio": [dict(offset=o,pc=p,operand=v) for o,p,v in STATUS_MMIO],
              "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [Path(__file__), ROOT/'tools/prepare_audio.py', ROOT/'snes/wram_clear.inc', ROOT/'snes/oam_live_half.inc', ROOT/'snes/camera_publish_safe.inc', ROOT/'snes/visible_row_phase.inc', ROOT/'snes/apu_length_gate.inc', ROOT/'snes/interrupt_policy.inc', ROOT/'snes/sprite_delta.inc', ROOT/'snes/planar_rows.inc', ROOT/'snes/planar_dma.inc', ROOT/'snes/hidden_direct_rows.inc', ROOT/'snes/palette_copy.inc', ROOT/'snes/pending_palette.asm', ROOT/'snes/pending_palette_queue.inc', ROOT/'snes/pending_palette.cfg', ROOT/'snes/early_audio_abi.inc', ROOT/'snes/early_gameplay_audio.asm', ROOT/'snes/direct_apu.inc', ROOT/'snes/bank_restore.inc', ROOT/'snes/sound_commit.inc', *sorted((ROOT / "snes").glob("native*"))]},
              "trace_manifest_sha256": [hashlib.sha256((p / "manifest.json").read_bytes()).hexdigest() for p in traces],
              "spc_source_sha256": deps["upernes"]["audio_sha256"],
              "spc_sha256": hashlib.sha256(patched_engine).hexdigest(),
              "experimental_noise_clock": experimental_noise_clock,
              "experimental_triangle_release": experimental_triangle_release,
              "experimental_pulse_sweep": experimental_pulse_sweep,
              "experimental_sweep_driver": experimental_sweep_driver,
              "experimental_retained_return_edge": experimental_retained_return_edge,
              "nmi_return_tail_sha256": hashlib.sha256((ROOT/'snes/nmi_return_tail.inc').read_bytes()).hexdigest(),
              "sweep_driver_layout": sweep_driver_layout,
              "sweep_driver_rom_offset": 0x120000 if experimental_sweep_driver else None,
              "sweep_driver_sources": {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                  for p in ('tools/build_sweep_driver.py', 'tools/build_sweep_packet.py',
                            'tools/build_sweep_kernel.py', 'snes/sweep_events.inc')}
                  if experimental_sweep_driver else None,
              "pulse_sweep_source_sha256": hashlib.sha256((ROOT/'tools/correct_pulse_sweep.py').read_bytes()).hexdigest() if experimental_pulse_sweep else None,
              "experimental_second_tick_prepare": experimental_second_tick_prepare,
              "experimental_second_tick_deadline": experimental_second_tick_deadline,
              "experimental_column_fetch": experimental_column_fetch,
              "experimental_main_phase_line": experimental_main_phase_line,
              "main_phase_sha256": hashlib.sha256((ROOT/'snes/main_phase.inc').read_bytes()).hexdigest() if experimental_main_phase_line is not None else None,
              "column_fetch_sha256": hashlib.sha256((ROOT/'snes/column_fetch.inc').read_bytes()).hexdigest() if experimental_column_fetch else None,
              "second_tick_deadline_sha256": hashlib.sha256((ROOT/'snes/second_tick_deadline.inc').read_bytes()).hexdigest() if experimental_second_tick_deadline else None,
              "second_tick_prepare_sha256": hashlib.sha256((ROOT/'snes/second_tick_prepare.inc').read_bytes()).hexdigest() if experimental_second_tick_prepare else None,
              "noise_clock_table": patched_engine[0x849:0x859].hex(),
              "spc_corrections": [{"offset": 0x28e, "before": 0xf3, "after": 0xf2,
                                   "reason": "select triangle right volume through DSP address port"}],
              "palette_sha256": hashlib.sha256(rgb).hexdigest(),
              "covered_instructions": len(seen), "patches": patched, "stub_bytes": len(stubs),
              "translated_helpers": [*([{"pc":0xEF11,"offset":0x1EF11,
                                      "entry":symbols['native_sprite_coordinates'],
                                      "preimage_sha256":hashlib.sha256(rom.prg[0x1EF11:0x1EF26]).hexdigest(),
                                      "kind":"unrolled original sprite coordinate additions; 8-bit arithmetic and exact flags"}]
                                      if experimental_sprite_coordinates else []),
                                     *([{"pc":0xE477,"offset":0x1E477,
                                      "entry":symbols['palette_copy_loop'],
                                      "preimage_sha256":hashlib.sha256(palette_preimage).hexdigest(),
                                      "kind":"guarded complete palette copy; original scalar fallback"}]
                                      if experimental_palette_copy else []),
                                     {"pc": 0xC90C, "offset": bulk_offset,
                                      "entry": symbols['bulk_ppu_byte'],
                                      "preimage_sha256": hashlib.sha256(bulk_preimage).hexdigest(),
                                      "kind": "whole decompression PPU byte writer"},
                                     {"pc": 0xC88F,"offset":rect_offset,
                                      "entry":symbols['bulk_rect_loop'],
                                      "preimage_sha256":hashlib.sha256(rect_preimage).hexdigest(),
                                      "kind":"guarded width-one rectangular fill; original fallback"},
                                     {"pc":0xC861,"offset":repeat_offset,
                                      "entry":symbols['bulk_repeat_loop'],
                                      "preimage_sha256":hashlib.sha256(repeat_preimage).hexdigest(),
                                      "kind":"repeated-byte fill using guarded rectangular engine"},
                                     {"pc": 0xC872, "offset": 0x1C872,
                                      "entry": symbols['bulk_literal_loop'],
                                      "preimage_sha256": hashlib.sha256(literal_preimage).hexdigest(),
                                      "kind": "guarded same-page CHR literal copy"},
                                     {"pc": 0xC8DB, "offset": source_offset,
                                      "entry": symbols['bulk_source_byte'],
                                      "preimage_sha256": hashlib.sha256(source_preimage).hexdigest(),
                                      "kind": "whole decompression source byte reader"},
                                     {"pc": 0xFCD6, "offset": 0x1FCD6,
                                      "entry": symbols['bulk_fill_loop'],
                                      "preimage_sha256": hashlib.sha256(fill_preimage).hexdigest(),
                                      "kind": "aligned increment-one page fill, setup preimage at FCB2"},
                                     {"pc": 0xFCF7, "offset": 0x1FCF7,
                                      "entry": symbols['bulk_attribute_loop'],
                                      "preimage_sha256": hashlib.sha256(attribute_preimage).hexdigest(),
                                      "kind": "guarded attribute fill with per-byte fallback"},
                                     {"pc": 0xC575, "offset": 0x1C575,
                                      "entry": symbols['bulk_ring_loop'],
                                      "preimage_sha256": hashlib.sha256(ring_preimage).hexdigest(),
                                      "kind": "graphics command ring byte loop"},
                                     *([{"pc": 0xC50B, "offset": 0x1C50B,
                                         "entry": symbols['native_ring_consumer'],
                                         "preimage_sha256": hashlib.sha256(consumer_preimage).hexdigest(),
                                         "kind": "bounded graphics command consumer"}]
                                       if experimental_native_ring_consumer else [])],
              "graphics_pipeline": "prepared dirty rows, whole CHR banks and bounded per-NMI DMA",
              "row_staging_layout": "split-low-high-4096-byte-planes" if experimental_planar_rows else "interleaved-16-bit-tile-words",
              "limits": {"vram_bytes_per_nmi": 2048, "chr_jobs_per_nmi": 1, "row_scan_per_nmi": 32,
                         "hidden_state2_vram_bytes_per_nmi": 4096 if experimental_hidden_dma else 2048,
                         "oam_bytes_per_nmi": 544, "cgram_bytes_per_nmi": 64,
                         "prepared_rows_per_call": experimental_gameplay_rows or 2,
                         "producer_row_scan_per_call": 128},
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
    parser.add_argument('--experimental-fastrom', action='store_true', help='Enable hardware FastROM timing for local regression; full-speed quality remains unverified')
    parser.add_argument('--experimental-raster', action='store_true', help='Enable unfinished raster worker; known missed-service regression, emulator testing only')
    parser.add_argument('--experimental-paired-audio', action='store_true', help='Opt-in two-byte SPC transport; emulator validation only')
    parser.add_argument('--experimental-triple-audio', action='store_true', help='Opt-in three-byte SPC transport; emulator validation only')
    parser.add_argument('--raster-line', type=int, default=30, help='Experimental worker target; requires --experimental-raster for nondefault values')
    parser.add_argument('--experimental-reset-audio', action='store_true', help='Opt-in fast combined pulse resets; requires paired audio, emulator validation only')
    parser.add_argument('--experimental-load-rows', type=int, choices=range(1, 9), help='Override non-gameplay prepared rows per load tick; emulator validation only')
    parser.add_argument('--experimental-gameplay-rows', type=int, choices=range(1, 9), help='Override visible-game prepared rows per tick; emulator validation only')
    parser.add_argument('--experimental-reuse-audio', action='store_true', help='Reuse unchanged paired packets while still running SPC synthesis; emulator validation only')
    parser.add_argument('--experimental-word-fill', action='store_true', help='Use 16-bit stores in checked repeated-byte page fills; emulator validation only')
    parser.add_argument('--experimental-transition-scan', action='store_true', help='Scan the complete row ring while an initial forced-blank publication is pending; emulator validation only')
    parser.add_argument('--experimental-fc60-defer', action='store_true', help='Move coroutine audio/graphics work to the next FC60 yield point; emulator validation only')
    parser.add_argument('--experimental-fc60-defer-audio', action='store_true', help='Move only coroutine audio work to the next FC60 yield point; emulator validation only')
    parser.add_argument('--experimental-fc60-defer-video', action='store_true', help='Move only coroutine graphics preparation to the next FC60 yield point; emulator validation only')
    parser.add_argument('--experimental-fc60-immediate-nmi', action='store_true', help='Allow the verified FC70 coroutine enable to observe a pending same-VBlank NMI; emulator validation only')
    parser.add_argument('--experimental-rect-dma', action='store_true', help='Use fixed-source WRAM DMA for guarded constant-byte rectangle fills; emulator validation only')
    parser.add_argument('--experimental-fill-dirty-batch', action='store_true', help='Batch dirty flags after an aligned four-page nametable fill; emulator validation only')
    parser.add_argument('--experimental-attribute-lookup', action='store_true', help='Use oracle-checked lookup tables for row attribute conversion; emulator validation only')
    parser.add_argument('--experimental-oam-dirty-gate', action='store_true', help='Skip sprite-shadow comparison until translated OAM writes make it necessary; emulator validation only')
    parser.add_argument('--experimental-oam-compare-unroll', action='store_true', help='Unroll unchanged sprite-shadow comparison eight words at a time; emulator validation only')
    parser.add_argument('--experimental-row-stores', action='store_true', help='Use oracle-checked fixed offsets for four-tile row groups; emulator validation only')
    parser.add_argument('--experimental-transition-prepare-defer', action='store_true', help='Retain forced-blank dirty graphics until the transition loader reaches state 2; emulator validation only')
    parser.add_argument('--experimental-gameplay-prepare-defer', action='store_true', help='Prepare active gameplay graphics after the original camera commit, with next-NMI fallback; emulator validation only')
    parser.add_argument('--experimental-chr-dirty-gate', action='store_true', help='Skip unchanged CHR job scans until a translated dependency write; emulator validation only')
    parser.add_argument('--experimental-sprite-unroll', action='store_true', help='Use oracle-checked unrolled NES-to-SNES OAM conversion; emulator validation only')
    parser.add_argument('--experimental-sprite-delta', action='store_true', help='Convert only changed sprite entries, with full pattern-half invalidation; emulator validation only')
    parser.add_argument('--experimental-suppress-duty-keyon', action='store_true', help='Change pulse duty samples without DSP hard key-on; emulator validation only')
    parser.add_argument('--experimental-camera-deadline', action='store_true', help='Return gameplay before port housekeeping, publish scroll at the camera commit, then service the retained job; emulator validation only')
    parser.add_argument('--experimental-deferred-game-nmi', action='store_true', help='Let an interrupted camera-bearing iteration finish before dispatching the retained original-game NMI body; emulator validation only')
    parser.add_argument('--experimental-deferred-reset-audio', action='store_true', help='Merge pulse reset/duty events and key on once after synthesis; emulator validation only')
    parser.add_argument('--experimental-ring-pointer-cache', action='store_true', help='Cache contiguous graphics-command shadow pointers between logical page boundaries; emulator validation only')
    parser.add_argument('--experimental-dirty-final-dma', action='store_true', help='Publish OAM and palette DMA only for producer generations that changed; emulator validation only')
    parser.add_argument('--experimental-control-presets', action='store_true', help='Four SNES-specific menu-selectable punch/kick/jump layouts; emulator validation only')
    parser.add_argument('--experimental-transition-game-first', action='store_true', help='Run original transition NMI work before forced-blank publication; emulator validation only')
    parser.add_argument('--experimental-row-scan', action='store_true', help='Skip clean producer row-flag groups eight at a time; emulator validation only')
    parser.add_argument('--experimental-native-ring-consumer', action='store_true', help='Drain the bounded original graphics-command ring through one native helper; emulator validation only')
    parser.add_argument('--experimental-transition-wait-prepare', action='store_true', help='Move forced-blank gameplay row preparation into existing end-of-iteration wait slack; emulator validation only')
    parser.add_argument('--experimental-native-command-producer', action='store_true', help='Inline the six command-ring pointer wraps in original CF04; emulator validation only')
    parser.add_argument('--experimental-native-ring-budget5', action='store_true', help='Drain at most five commands only while a native forced-blank transition is active; emulator validation only')
    parser.add_argument('--experimental-oam-word-copy',action='store_true',help='Copy low-WRAM OAM pages with native direct-page words; emulator validation only')
    parser.add_argument('--experimental-hidden-rows',type=int,choices=range(1,17),help='Override row conversion only during state-2 hidden gameplay loading; emulator validation only')
    parser.add_argument('--experimental-alias-word-copy',action='store_true',help='Copy mirrored staged rows with native words and preserved queue ownership; emulator validation only')
    parser.add_argument('--experimental-hidden-dma',action='store_true',help='Allow 4096 VRAM bytes only in state-2 forced-blank publication; emulator validation only')
    parser.add_argument('--experimental-fused-alias-rows',action='store_true',help='Store dirty mirrored rows during tile conversion, preserving queued snapshots; requires attribute lookup')
    parser.add_argument('--experimental-planar-rows',action='store_true',help='Use split low/high row snapshots and two bounded VRAM DMA passes; emulator validation only')
    parser.add_argument('--experimental-hidden-row-run',action='store_true',help='Batch contiguous immutable rows only in forced-blank state 2; emulator validation only')
    parser.add_argument('--experimental-fast-publisher',action='store_true',help='Enter the native video consumer through its FastROM mirror; emulator validation only')
    parser.add_argument('--experimental-hidden-direct-rows',action='store_true',help='Upload unqueued NES rows directly during forced-blank state 2; emulator validation only')
    parser.add_argument('--experimental-hidden-high-cache',action='store_true',help='Reuse immutable attribute high bytes within one hidden-load producer call; emulator validation only')
    parser.add_argument('--experimental-hidden-direct-pair',action='store_true',help='Batch eligible hidden even/odd rows without changing the row budget; emulator validation only')
    parser.add_argument('--experimental-chr-read-cache',action='store_true',help='Cache one resolved CHR page until any mapper transaction; emulator validation only')
    parser.add_argument('--experimental-chr-read-pair',action='store_true',help='Resolve guarded buffered CHR source-read pairs once; emulator validation only')
    parser.add_argument('--experimental-hidden-sprite-defer',action='store_true',help='Defer hidden sprite preparation while a required unqueued row prevents exposure; emulator validation only')
    parser.add_argument('--experimental-direct-apu',action='store_true',help='Guarded direct dynamic APU write ABI; emulator validation only')
    parser.add_argument('--experimental-bank-restore',action='store_true',help='Atomic direct FF29 paired-bank restoration; emulator validation only')
    parser.add_argument('--experimental-sound-commit',action='store_true',help='Fused original sound-shadow/channel/write helper; emulator validation only')
    parser.add_argument('--experimental-pending-palette-all-levels',action='store_true',help='Preview safely ordered write-head palettes at every fade level; emulator validation only')
    parser.add_argument('--experimental-camera-nmi-reenable',action='store_true',help='Preserve a fresh VBlank edge at camera completion; emulator validation only')
    parser.add_argument('--experimental-early-deferred-audio',action='store_true',help='Service retained gameplay sound before resuming the camera; emulator validation only')
    parser.add_argument('--experimental-late-prepare-guard',action='store_true',help='Retain late visible graphics work for the next ordinary NMI; emulator validation only')
    parser.add_argument('--experimental-palette-copy',action='store_true',help='Guarded whole original palette-copy loop; emulator validation only')
    parser.add_argument('--experimental-pending-palette',action='store_true',help='Prepare an eligible original palette before the same NMI final upload; emulator validation only')
    parser.add_argument('--experimental-pending-palette-write-head',action='store_true',help='Permit preview before one fade-budget write command, never before a read head; emulator validation only')
    parser.add_argument('--experimental-oam-live-half',action='store_true',help='Initialize full OAM once, then publish the 64 live slots; emulator validation only')
    parser.add_argument('--experimental-camera-safe-publish',action='store_true',help='Keep live street HDMA entries immutable after the drawing deadline; emulator validation only')
    parser.add_argument('--experimental-camera-vblank-commit',action='store_true',help='Publish committed street camera before optional VBlank graphics transfers; emulator validation only')
    parser.add_argument('--experimental-static-camera-arm',action='store_true',help='Arm retained NMI after fade-in even before camera motion; emulator validation only')
    parser.add_argument('--experimental-camera-line30',action='store_true',help='Permit camera copies through line30; unpromoted latency experiment')
    parser.add_argument('--experimental-visible-attribute-cache',action='store_true',help='Reuse immutable palette/pattern words within one row-preparation call; emulator validation only')
    parser.add_argument('--experimental-visible-row-phase',action='store_true',help='Prepare stable gameplay rows on tick one and defer rows on tick two; emulator validation only')
    parser.add_argument('--experimental-sprite-coordinates',action='store_true',help='Unroll the original pair of sprite-coordinate additions with identical 8-bit arithmetic')
    parser.add_argument('--experimental-noise-clock',action='store_true',help='Quantize NTSC noise periods to nearest DSP clock; not complete NES noise fidelity')
    parser.add_argument('--experimental-triangle-release',action='store_true',help='Diagnostic mono triangle attack/release; paired fast-reset audio only, not qualified for deployment')
    parser.add_argument('--experimental-pulse-sweep',action='store_true',help='Correct pulse-1 sweep target arithmetic with matched SPC cycle count; experimental game validation')
    parser.add_argument('--experimental-sweep-driver',action='store_true',help='Experimental shared live sweep clock, write-event transport and mono pulse DSP publisher; not hardware qualified')
    parser.add_argument('--experimental-retained-return-edge',action='store_true',help='Preserve fresh NMI when the retained camera interrupt returns during VBlank; validation only')
    parser.add_argument('--experimental-second-tick-prepare',action='store_true',help='Retain stable tick-2 graphics preparation until camera completion; emulator validation only')
    parser.add_argument('--experimental-second-tick-deadline',action='store_true',help='Leave late camera-tail graphics preparation pending for interrupt fallback; experimental budget')
    parser.add_argument('--experimental-column-fetch',action='store_true',help='Unroll original 20-row column fetch without changing interrupt policy')
    parser.add_argument('--experimental-main-phase-line',type=int,help='Earliest stable-game iteration start within current frame; original tick cadence retained')
    parser.add_argument('--experimental-sprite-position',action='store_true',help='Fuse original signed sprite offsets and coordinate additions; no interrupt-policy change')
    parser.add_argument('--experimental-joypad-poll',action='store_true',help='Consume latched controller bytes without repeated generic I/O dispatch')
    parser.add_argument('--experimental-deferred-resume-line',type=int,choices=range(240,251),help='Experimental retained-NMI resume threshold after bounded video publication')
    args = parser.parse_args()
    # Keep experimental copy policy explicit in the build manifest.
    build(args.rom, args.trace, args.out, args.experimental_fastrom, args.experimental_raster, args.experimental_paired_audio, args.raster_line, args.experimental_reset_audio, args.experimental_triple_audio, args.experimental_load_rows, args.experimental_reuse_audio, args.experimental_word_fill, args.experimental_transition_scan, args.experimental_fc60_defer, args.experimental_rect_dma, args.experimental_fc60_defer_audio, args.experimental_fc60_defer_video, args.experimental_fc60_immediate_nmi, args.experimental_fill_dirty_batch, args.experimental_attribute_lookup, args.experimental_oam_dirty_gate, args.experimental_oam_compare_unroll, args.experimental_row_stores, args.experimental_transition_prepare_defer, args.experimental_gameplay_prepare_defer, args.experimental_chr_dirty_gate, args.experimental_sprite_unroll, args.experimental_suppress_duty_keyon, args.experimental_camera_deadline, args.experimental_deferred_game_nmi, args.experimental_deferred_reset_audio, args.experimental_gameplay_rows, args.experimental_ring_pointer_cache, args.experimental_dirty_final_dma, args.experimental_transition_game_first, args.experimental_row_scan, args.experimental_native_ring_consumer, args.experimental_transition_wait_prepare, args.experimental_native_command_producer, args.experimental_native_ring_budget5, args.experimental_control_presets, args.experimental_sprite_delta, args.experimental_oam_word_copy, args.experimental_hidden_rows, args.experimental_alias_word_copy,
          experimental_hidden_high_cache=args.experimental_hidden_high_cache,
          experimental_hidden_sprite_defer=args.experimental_hidden_sprite_defer,
          experimental_direct_apu=args.experimental_direct_apu,
          experimental_bank_restore=args.experimental_bank_restore,
          experimental_sound_commit=args.experimental_sound_commit,
          experimental_hidden_direct_pair=args.experimental_hidden_direct_pair,
          experimental_chr_read_cache=args.experimental_chr_read_cache,
          experimental_chr_read_pair=args.experimental_chr_read_pair,
          experimental_oam_live_half=args.experimental_oam_live_half,
          experimental_camera_safe_publish=args.experimental_camera_safe_publish,
          experimental_camera_vblank_commit=args.experimental_camera_vblank_commit,
          experimental_static_camera_arm=args.experimental_static_camera_arm,
          experimental_camera_line30=args.experimental_camera_line30,
          experimental_visible_attribute_cache=args.experimental_visible_attribute_cache,
          experimental_visible_row_phase=args.experimental_visible_row_phase,
          experimental_sprite_coordinates=args.experimental_sprite_coordinates,
          experimental_noise_clock=args.experimental_noise_clock,
          experimental_triangle_release=args.experimental_triangle_release,
          experimental_pulse_sweep=args.experimental_pulse_sweep,
          experimental_sweep_driver=args.experimental_sweep_driver,
          experimental_retained_return_edge=args.experimental_retained_return_edge,
          experimental_second_tick_prepare=args.experimental_second_tick_prepare,
          experimental_second_tick_deadline=args.experimental_second_tick_deadline,
          experimental_column_fetch=args.experimental_column_fetch,
          experimental_main_phase_line=args.experimental_main_phase_line,
          experimental_sprite_position=args.experimental_sprite_position,
          experimental_joypad_poll=args.experimental_joypad_poll,
          experimental_deferred_resume_line=args.experimental_deferred_resume_line,
          experimental_pending_palette_all_levels=args.experimental_pending_palette_all_levels,
          experimental_hidden_dma=args.experimental_hidden_dma, experimental_fused_alias_rows=args.experimental_fused_alias_rows,
          experimental_planar_rows=args.experimental_planar_rows, experimental_hidden_row_run=args.experimental_hidden_row_run,
          experimental_fast_publisher=args.experimental_fast_publisher, experimental_hidden_direct_rows=args.experimental_hidden_direct_rows,
          experimental_camera_nmi_reenable=args.experimental_camera_nmi_reenable, experimental_early_deferred_audio=args.experimental_early_deferred_audio,
          experimental_late_prepare_guard=args.experimental_late_prepare_guard,
          experimental_palette_copy=args.experimental_palette_copy,
          experimental_pending_palette=args.experimental_pending_palette,
          experimental_pending_palette_write_head=args.experimental_pending_palette_write_head)
