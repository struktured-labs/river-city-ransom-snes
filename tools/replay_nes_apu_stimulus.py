"""Replay a captured game APU write prefix on a real NES core, frame-quantized."""
import argparse
import csv
import ctypes as C
import json
from pathlib import Path
import subprocess

from tools import smoke_libretro as smoke
from tools.benchmark_report import sha, verify_capture


def publication_writes(rows):
    """Retain ordered writes, but schedule them at their actual packet's frame.

    This deliberately models publication cadence, not original CPU write time.
    Packet boundaries are taken only from the trace; no waveform alignment.
    """
    pending, packet, result, mapping = [], [], [], []
    previous = 0
    packet_number = 0
    for ordinal, row in enumerate(rows):
        if len(row) != 8 or row[0] not in ('P', 'W'):
            raise ValueError('Malformed publication row')
        frame, index, value = int(row[1]), int(row[5]), int(row[6])
        if frame < previous or frame < 1 or not 0 <= value <= 255:
            raise ValueError('Invalid publication ordering/value')
        previous = frame
        if row[0] == 'W':
            if packet:
                raise ValueError('Write interleaved with publication')
            pending.append((ordinal, row))
            continue
        if index != len(packet):
            raise ValueError('Missing/reordered publication byte')
        packet.append(value)
        if len(packet) == 23:
            packet_number += 1
            for source_ordinal, original in pending:
                shifted = list(original)
                shifted[1] = str(frame)
                result.append(shifted)
                mapping.append(dict(trace_row=source_ordinal, write_frame=int(original[1]),
                                    publication_frame=frame, packet=packet_number))
            pending, packet = [], []
    if packet or pending or not packet_number:
        raise ValueError('Unfinished/missing publication')
    return result, mapping


def pack_writes(rows, frames, banked=False):
    if not 1 <= frames <= 65535:
        raise ValueError('Frame counter capacity exceeded')
    grouped = [[] for _ in range(frames)]
    previous = 0
    for row in rows:
        if len(row) != 8 or row[0] not in ('P', 'W'):
            raise ValueError('Malformed bus row')
        if row[0] != 'W':
            continue
        frame, index, value = int(row[1]), int(row[5]), int(row[6])
        if frame < previous or frame < 1 or not 0 <= value <= 255:
            raise ValueError('Invalid write ordering/value')
        previous = frame
        if index in (16, 17, 18, 19, 20, 22) or not 0 <= index < 24 or (index == 21 and value & 16):
            raise ValueError('Unsupported DMC/DMA/controller stimulus')
        if frame <= frames:
            grouped[frame-1].append((index, value))
    if any(len(writes) > 128 for writes in grouped):
        raise ValueError('Frame exceeds conservative NES execution budget')
    payload = bytes(byte for writes in grouped for byte in
                    [len(writes), *[v for pair in writes for v in pair]])
    if len(payload) > (7*16384 if banked else 32000):
        raise ValueError('Stimulus exceeds ROM capacity')
    if sum(map(len, grouped)) > 65535:
        raise ValueError('Write counter capacity exceeded')
    if not any(grouped):
        raise ValueError('Empty stimulus')
    return payload, grouped


def capture_player(core, rom, out, grouped):
    original = C.CDLL
    timeline, retained = [], []
    samples = 0
    current = 0
    expected_registers = bytearray(24)
    expected_count = 0
    final_ram = None
    banked = rom.read_bytes()[6] == 0x20
    def loader(path):
        nonlocal samples, current, expected_count, final_ram
        lib = original(path)
        for name in ('retro_set_audio_sample_batch', 'retro_set_audio_sample'):
            setter = getattr(lib, name)
            def register(callback, setter=setter, batch=name.endswith('_batch')):
                @type(callback)
                def hooked(*args):
                    nonlocal samples
                    result = callback(*args)
                    samples += args[1] if batch else 1
                    return result
                retained.append(hooked)
                setter.argtypes = [type(callback)]
                setter(hooked)
            setattr(lib, name, register)
        run = lib.retro_run
        def step():
            nonlocal current, expected_count, final_ram
            start = samples
            run()
            if lib.retro_get_memory_size(2) != 2048:
                raise ValueError('Expected NES RAM')
            ram = C.string_at(lib.retro_get_memory_data(2), 2048)
            final_ram = ram
            frame = int.from_bytes(ram[0x200:0x202], 'little')
            if not ram[0x203] or frame == current:
                return
            if frame != current+1 or frame > len(grouped):
                raise ValueError('Skipped/reordered stimulus frame')
            for index, value in grouped[frame-1]:
                expected_registers[index] = value
                expected_count += 1
            if (ram[0x220:0x238] != expected_registers or
                    int.from_bytes(ram[0x204:0x206], 'little') != expected_count):
                (out/'failure.ram').write_bytes(ram)
                raise ValueError(f'Executed write shadow/count differs at frame {frame}: '
                    f'count {int.from_bytes(ram[0x204:0x206], "little")} != {expected_count}; '
                    f'shadow {ram[0x220:0x238].hex()} != {expected_registers.hex()}')
            if banked:
                consumed = frame+2*expected_count
                if (ram[3] != consumed//16384 or
                        int.from_bytes(ram[:2], 'little') != 0x8000+consumed%16384):
                    raise ValueError('Executed bank/pointer differs')
            timeline.append(dict(source_frame=frame, start_sample=start, end_sample=samples,
                                 apu_status=ram[0x206], completed_writes=expected_count))
            current = frame
        lib.retro_run = step
        return lib
    smoke.C.CDLL = loader
    try:
        receipt = smoke.run(core, rom, len(grouped)+12, out/'audio.wav', kind='render')
    finally:
        smoke.C.CDLL = original
    if current != len(grouped) or not final_ram[0x202]:
        raise ValueError('Incomplete stimulus execution')
    if receipt['audio_peak'] == 0:
        raise ValueError('Executed stimulus is silent')
    (out/'memory.ram').write_bytes(final_ram)
    (out/'timeline.json').write_text(json.dumps(timeline, indent=2)+'\n')
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def run(capture, bus, provenance, core, frames, out, banked=False, timing='cpu-frame'):
    receipt, _ = verify_capture(capture)
    proof = json.loads((provenance/'report.json').read_text())
    if (not proof['passed'] or proof['rom_sha256'] != receipt['rom_sha256'] or
            proof['audio_sha256'] != receipt['audio_sha256']):
        raise ValueError('Different or failed provenance')
    for file, digest in proof['sources'].items():
        if sha(Path(file)) != digest:
            raise ValueError('Changed provenance input: '+file)
    if receipt['audio_bus_trace']['sha256'] != sha(bus) or proof['sources'].get(str(bus)) != sha(bus):
        raise ValueError('Bus not bound to checked capture/provenance')
    if not 1 <= frames <= receipt['frames']:
        raise ValueError('Invalid prefix length')
    with bus.open() as source:
        rows = list(csv.reader(source))
    mapping = None
    if timing == 'publication-frame':
        rows, mapping = publication_writes(rows)
    payload, grouped = pack_writes(rows, frames, banked)
    out.mkdir(parents=True, exist_ok=False)
    if mapping is not None:
        (out/'publication-map.json').write_text(json.dumps(mapping, indent=2)+'\n')
    (out/'stimulus.bin').write_bytes(payload)
    subprocess.run(['.deps/cc65/bin/ca65', '-g', '-D', f'SOURCE_FRAMES={frames}',
                    '-D', f'BANKED={int(banked)}', '--bin-include-dir', str(out),
                    '-o', str(out/'player.o'), 'snes/nes_apu_stimulus.asm'], check=True)
    rom = out/'player.nes'
    config = Path('snes/nes_apu_stimulus_banked.cfg' if banked else 'snes/nes_disabled_reload.cfg')
    subprocess.run(['.deps/cc65/bin/ld65', '-C', str(config),
                    '-Ln', str(out/'player.lbl'), '-o', str(rom), str(out/'player.o')], check=True)
    if banked:
        compiled = rom.read_bytes()
        if len(compiled) != 16+16384+8192:
            raise ValueError('Unexpected fixed-bank image')
        rom.write_bytes(compiled[:16]+payload.ljust(7*16384, b'\xff')+compiled[16:])
    result = capture_player(core, rom, out, grouped)
    labels = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
              for r in (out/'player.lbl').read_text().splitlines()}
    muted = bytearray(rom.read_bytes())
    code_base = 16+7*16384-0xC000 if banked else 16-0x8000
    offset = code_base+labels['apu_store']
    if muted[offset:offset+3] != bytes.fromhex('9d0040'):
        raise ValueError('Unknown physical APU store')
    muted[offset+1] = 0x20  # Redirect physical writes to unmapped expansion I/O.
    mutant = out/'silent-control.nes'
    mutant.write_bytes(muted)
    # A fresh process avoids all static emulator state; count/shadow can still
    # look correct while physical APU writes are broken. Require actual sound.
    negative = subprocess.run(['python3', '-m', 'tools.replay_nes_apu_stimulus',
        '--control-rom', str(mutant), '--core', str(core), '--control-stimulus', str(out/'stimulus.bin'),
        '--frames', str(frames), '--out', str(out/'silent-control')], capture_output=True, text=True, timeout=120)
    (out/'silent-control.log').write_text(negative.stdout+negative.stderr)
    if negative.returncode == 0 or 'Executed stimulus is silent' not in negative.stderr:
        raise ValueError('Silent physical-write mutant not rejected')
    empty = bytearray(rom.read_bytes())
    offset = code_base+labels['empty_count_check']
    if empty[offset:offset+2] != bytes.fromhex('c900'):
        raise ValueError('Unknown empty-frame guard')
    empty[offset:offset+2] = b'\xea\xea'
    empty_rom = out/'empty-frame-control.nes'
    empty_rom.write_bytes(empty)
    rejected = subprocess.run(['python3', '-m', 'tools.replay_nes_apu_stimulus',
        '--control-rom', str(empty_rom), '--core', str(core), '--control-stimulus', str(out/'stimulus.bin'),
        '--frames', str(frames), '--out', str(out/'empty-frame-control')],
        capture_output=True, text=True, timeout=120)
    (out/'empty-frame-control.log').write_text(rejected.stdout+rejected.stderr)
    if rejected.returncode == 0 or 'Executed write shadow/count differs at frame 1' not in rejected.stderr:
        raise ValueError('Empty-frame control not rejected')
    bank_sources = []
    if banked and len(payload) > 16384:
        broken = bytearray(rom.read_bytes())
        offset = code_base+labels['bank_store']
        if broken[offset:offset+3] != bytes.fromhex('9d00ff'):
            raise ValueError('Unknown bank switch')
        broken[offset:offset+3] = b'\xea'*3
        bank_rom = out/'bank-control.nes'
        bank_rom.write_bytes(broken)
        rejected = subprocess.run(['python3', '-m', 'tools.replay_nes_apu_stimulus',
            '--control-rom', str(bank_rom), '--core', str(core),
            '--control-stimulus', str(out/'stimulus.bin'), '--frames', str(frames),
            '--out', str(out/'bank-control')], capture_output=True, text=True, timeout=120)
        (out/'bank-control.log').write_text(rejected.stdout+rejected.stderr)
        if rejected.returncode == 0 or 'Executed write shadow/count differs' not in rejected.stderr:
            raise ValueError('Missing bank switch not rejected')
        bank_sources = [bank_rom, out/'bank-control.log', out/'bank-control/failure.ram']
    sources = bank_sources+[Path(__file__), Path('snes/nes_apu_stimulus.asm'), config,
        Path('tools/smoke_libretro.py'), provenance/'report.json', capture/'capture.json', bus, core,
        rom, out/'stimulus.bin', out/'timeline.json', out/'audio.wav', out/'receipt.json',
        out/'memory.ram', mutant, out/'silent-control.log', empty_rom, out/'empty-frame-control.log',
        out/'empty-frame-control/failure.ram', Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65')]
    if mapping is not None:
        sources.append(out/'publication-map.json')
    report = dict(passed=True, source_frames=frames, writes=sum(map(len, grouped)),
        timing=timing,
        writes_moved_to_later_frame=sum(r['publication_frame'] > r['write_frame'] for r in mapping)
            if mapping is not None else 0,
        mapper=2 if banked else 0, bank_crossings=len(payload)//16384 if banked else 0,
        missing_bank_switch_mutant_rejected=bool(bank_sources),
        packed_bytes=len(payload), audio_peak=result['audio_peak'],
        silent_physical_write_mutant_rejected=True, empty_frame_mutant_rejected=True,
        sources={str(p): sha(p) for p in sources},
        scope='Executed asset-free NES stimulus from initial state, preserving every captured '
              'APU write and order, one source frame per VBlank. '+
              ('Writes scheduled at actual packet-completion frames, not CPU-write frames. '
               if mapping is not None else 'Writes scheduled at CPU-write host frames. ')+
              'Intra-frame SNES beam times are '
              'retimed, not NES-cycle-equivalent. Actual sound and frame/count/register shadow '
              'checked; not individual APU write-site observation or waveform fidelity certification.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sources','scope')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'bus', 'provenance', 'core', 'out', 'control-rom', 'control-stimulus'):
        p.add_argument('--'+name, type=Path, required=name in ('core','out'))
    p.add_argument('--frames', type=int, required=True)
    p.add_argument('--banked', action='store_true')
    p.add_argument('--timing', choices=('cpu-frame', 'publication-frame'), default='cpu-frame')
    args = vars(p.parse_args())
    control = args.pop('control_rom')
    packed = args.pop('control_stimulus')
    if control:
        data = packed.read_bytes()
        grouped, cursor = [], 0
        for _ in range(args['frames']):
            count = data[cursor]
            cursor += 1
            grouped.append(list(zip(data[cursor:cursor+count*2:2], data[cursor+1:cursor+count*2:2])))
            cursor += count*2
        if cursor != len(data):
            raise ValueError('Malformed control stimulus')
        args['out'].mkdir()
        capture_player(args['core'], control, args['out'], grouped)
    else:
        if any(args[k] is None for k in ('capture','bus','provenance')):
            p.error('capture, bus and provenance required')
        run(**args)
