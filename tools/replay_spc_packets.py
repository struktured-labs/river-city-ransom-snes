"""Build/execute an asset-free replay with the cartridge's exact SPC engine.

Publication frames are retained, but within-frame placement is deliberately
VBlank-quantized. This is a hardware/emulator comparison fixture, not the game.
"""
import argparse
import csv
import ctypes as C
import json
import os
from pathlib import Path
import struct
import subprocess

from tools import smoke_libretro as smoke
from tools.audit_main_display_latency import bound_report
from tools.audit_sweep_driver_game import sites
from tools.benchmark_report import sha, verify_capture


def packets(rows, frames):
    grouped = [[] for _ in range(frames)]
    packet = []
    previous = 0
    for row in rows:
        if len(row) != 8 or row[0] not in ('P','W'):
            raise ValueError('Invalid source bus')
        frame, index, value = int(row[1]),int(row[5]),int(row[6])
        if not 1 <= frame <= frames or frame < previous or not 0 <= value < 256:
            raise ValueError('Invalid source ordering/value')
        previous = frame
        if row[0] == 'W':
            if packet:
                raise ValueError('Interleaved packet')
            continue
        if index != len(packet):
            raise ValueError('Missing/reordered packet byte')
        packet.append(value)
        if len(packet) == 23:
            grouped[frame-1].append(bytes(packet))
            packet = []
    if packet or not any(grouped) or any(len(p)>1 for p in grouped):
        raise ValueError('Incomplete/empty/multi-packet source')
    payload = b''.join(bytes((len(p),))+b''.join(p) for p in grouped)
    if len(payload) > 65535:
        raise ValueError('Replay exceeds single-bank stream')
    return grouped,payload


def build(candidate, capture, provenance, out, mutation=None):
    if mutation not in (None,'double-frame','wrong-port'):
        raise ValueError('Unknown executed mutation')
    proof = bound_report(provenance)
    receipt, rows = verify_capture(capture)
    m, _, _ = sites(candidate)
    if not proof['passed'] or not proof['observer_neutral'] or not receipt['capture_complete']:
        raise ValueError('Need complete neutral transport proof')
    if proof['rom_sha256'] != receipt['rom_sha256'] or m['rom_sha256'] != receipt['rom_sha256']:
        raise ValueError('Different candidate')
    bus = Path(receipt['audio_bus_trace']['path'])
    if proof['sources'].get(str(bus)) != sha(bus):
        raise ValueError('Unbound source bus')
    with bus.open() as f:
        grouped,payload = packets(csv.reader(f),len(rows))
    out.mkdir(parents=True,exist_ok=False)
    (out/'stream.bin').write_bytes(payload)
    image = (candidate/'native-cpu.sfc').read_bytes()
    offset = m['sweep_driver_rom_offset']
    engine = image[offset:offset+m['sweep_driver_layout']['engine_bytes']]
    (out/'engine.bin').write_bytes(engine)
    defs = ['-D',f'SOURCE_FRAMES={len(rows)}','-D','EXPERIMENTAL_SWEEP_EVENTS=1',
            '-D',f'SWEEP_DRIVER_BYTES={len(engine)}','-D','AUDIO_PAIR=1','-D','AUDIO_FAST_RESET=1']
    if mutation == 'double-frame':
        defs += ['-D','DOUBLE_FRAME_WAIT=1']
    subprocess.run(['.deps/cc65/bin/ca65','-g','-I','snes',*defs,'-o',str(out/'player.o'),
                    'snes/apu_packet_replay.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-Ln',str(out/'player.lbl'),
                    '-o',str(out/'player.bin'),str(out/'player.o')],check=True)
    rom = bytearray(2097152)
    rom[0x8000:0x10000] = (out/'player.bin').read_bytes()
    rom[0x120000:0x120000+len(engine)] = engine
    rom[0x130000:0x130000+len(payload)] = payload
    if mutation == 'wrong-port':
        pattern = bytes.fromhex('b9000a8d4121')
        code = rom[0x8000:0xffc0]
        if code.count(pattern) != 1:
            raise ValueError('Nonunique packet data-port mutation')
        rom[0x8000+code.index(pattern)+4] = 0x43
    rom[0xffdc:0xffe0] = b'\xff\xff\0\0'
    total = sum(rom)&65535
    struct.pack_into('<HH',rom,0xffdc,total^65535,total)
    (out/'player.sfc').write_bytes(rom)
    report = dict(source_frames=len(rows), packets=sum(map(len,grouped)),
        source_rom_sha256=m['rom_sha256'], rom_sha256=sha(out/'player.sfc'),
        spc_sha256=sha(out/'engine.bin'), source_capture=str(capture), mutation=mutation,
        sources={str(p):sha(p) for p in (Path(__file__),Path('snes/apu_packet_replay.asm'),
            Path('snes/native_audio.asm'),Path('snes/native_spc_frame.inc'),Path('snes/wram_clear.inc'),
            candidate/'manifest.json',candidate/'native-cpu.sfc',capture/'capture.json',
            provenance,bus,out/'engine.bin',out/'stream.bin',out/'player.sfc')},
        scope=__doc__, release_ready=False)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),frames=len(rows),packets=report['packets'],rom_sha256=report['rom_sha256'])))


def execute(core, fixture, out):
    manifest = bound_report(fixture/'manifest.json')
    raw = (fixture/'stream.bin').read_bytes()
    grouped = []; cursor = 0
    for _ in range(manifest['source_frames']):
        count=raw[cursor]; cursor+=1
        grouped.append([raw[cursor:cursor+23]] if count else [])
        cursor+=count*23
    if cursor != len(raw):
        raise ValueError('Malformed replay stream')
    out.mkdir(parents=True,exist_ok=False)
    original = C.CDLL
    timeline = []; retained = []; samples = 0; calls = 0; current = 0; count = 0
    packet = bytes(23)
    def loader(path):
        nonlocal samples,calls,current,count,packet
        lib=original(path)
        for name in ('retro_set_audio_sample_batch','retro_set_audio_sample'):
            setter=getattr(lib,name)
            def register(callback,setter=setter,batch=name.endswith('_batch')):
                @type(callback)
                def hooked(*args):
                    nonlocal samples
                    result=callback(*args);samples+=args[1] if batch else 1
                    return result
                retained.append(hooked);setter.argtypes=[type(callback)];setter(hooked)
            setattr(lib,name,register)
        run=lib.retro_run
        def step():
            nonlocal calls,current,count,packet
            start=samples;run();calls+=1
            ram=C.string_at(lib.retro_get_memory_data(2),32768)
            if ram[0x1c0b]:
                (out/'failure.ram').write_bytes(ram)
                raise ValueError('Replay fault: source frame '+str(current))
            frame=int.from_bytes(ram[0x1800:0x1802],'little')
            if frame==current:
                return
            if frame!=current+1 or (timeline and calls!=timeline[-1]['host_frame']+1):
                raise ValueError('Missing source frame/cadence')
            expected=grouped[frame-1];count+=len(expected)
            if expected:packet=expected[-1]
            if int.from_bytes(ram[0x1802:0x1804],'little')!=count or ram[0xa00:0xa17]!=packet:
                raise ValueError('Wrong packet count/shadow')
            timeline.append(dict(source_frame=frame,host_frame=calls,start_sample=start,end_sample=samples,
                                 packets=count,packet=packet.hex()))
            current=frame
        lib.retro_run=step
        return lib
    smoke.C.CDLL=loader
    try:
        receipt=smoke.run(core,fixture/'player.sfc',manifest['source_frames']+360,
            out/'audio.wav',kind='adapter',screenshot=out/'last.png',ram_path=out/'memory.ram')
    except Exception as error:
        (out/'timeline.json').write_text(json.dumps(timeline,indent=2)+'\n')
        (out/'report.json').write_text(json.dumps(dict(passed=False,error=str(error),
            frames_observed=current,host_calls=calls,sources={str(p):sha(p) for p in (
                Path(__file__),Path('tools/smoke_libretro.py'),core,fixture/'manifest.json',
                fixture/'player.sfc',out/'timeline.json')}),indent=2)+'\n')
        raise
    finally:
        smoke.C.CDLL=original
    if current!=manifest['source_frames'] or not (out/'memory.ram').read_bytes()[0x1804]:
        raise ValueError('Incomplete replay')
    (out/'timeline.json').write_text(json.dumps(timeline,indent=2)+'\n')
    result=dict(passed=True,frames=current,packets=count,receipt=receipt,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/smoke_libretro.py'),core,
            fixture/'manifest.json',fixture/'player.sfc',out/'audio.wav',out/'timeline.json',out/'memory.ram')},
        scope='Every emitted frame checked for contiguous source index, packet count, shadow and '
              'one host-frame cadence; native packet engine and sender. Actual receiver observation '
              'and physical comparison are separate requirements.',physical_audio_verified=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,frames=current,packets=count)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='mode',required=True)
    b=sub.add_parser('build')
    for name in ('candidate','capture','provenance','out'):b.add_argument('--'+name,type=Path,required=True)
    b.add_argument('--mutation',choices=('double-frame','wrong-port'))
    e=sub.add_parser('execute')
    for name in ('core','fixture','out'):e.add_argument('--'+name,type=Path,required=True)
    args=vars(p.parse_args());mode=args.pop('mode')
    (build if mode=='build' else execute)(**args)
