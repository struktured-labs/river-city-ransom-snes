"""Matched isolated pulse-2 reset stimuli for NES and the exact current SPC engine.

Eight held-tone cases: four duty settings at periods $00FD and $06C6 (the latter
appears at the retained gameplay restart). Synthetic diagnostic, not game replay.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.replay_nes_apu_stimulus import capture_player


def stimulus(suppress=False):
    nes,packets,cases = [],[],[]
    for period in (0xfd,0x6c6):
        for duty in range(4):
            start = len(nes)+1
            control = 0x3f | (duty << 6)
            events = []
            for frame in range(1,129):
                p = bytearray(23)
                p[4:8] = bytes((control,8,period&255,period>>8))
                p[21] = 2
                if frame == 1:
                    writes = [(0x17,0x40),(0x15,2),(4,control),(5,8),(6,period&255),(7,period>>8)]
                    p[20],p[22] = 0x72,2
                elif frame in (33,65,97):
                    # Redirect only periodic writes to the disabled other pulse;
                    # same CPU instruction/data count, not a missing-write timing change.
                    writes = [(3 if suppress else 7,period>>8)]
                    p[20],p[22] = (0,0) if suppress else (0x20,2)
                    events.append(len(nes)+1)
                else:
                    writes = []
                nes.append(writes); packets.append(bytes(p))
            cases.append(dict(first_frame=start,last_frame=len(nes),period=period,duty=duty,
                              control=control,reset_frames=events))
    for frame in range(60):
        nes.append([(0x15,0)] if frame==0 else [])
        packets.append(bytes(23))
    return nes,packets,cases


def build(candidate,out):
    if out.exists(): raise ValueError('Fresh diagnostic required')
    meta = json.loads((candidate/'manifest.json').read_text())
    if sha(candidate/'native-cpu.sfc') != meta['rom_sha256']:
        raise ValueError('Unbound current cartridge')
    at,size=meta['sweep_driver_rom_offset'],meta['sweep_driver_layout']['engine_bytes']
    engine=(candidate/'native-cpu.sfc').read_bytes()[at:at+size]
    if hashlib.sha256(engine).hexdigest()!=meta['spc_sha256']:
        raise ValueError('Different current SPC engine')
    out.mkdir(parents=True)
    for variant in ('reset','suppressed'):
        grouped,packets,cases=stimulus(variant=='suppressed')
        for system in ('nes','snes'):
            folder=out/(system+'-'+variant);folder.mkdir()
            paths=[Path(__file__),candidate/'manifest.json',candidate/'native-cpu.sfc',
                   Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65')]
            if system=='nes':
                payload=bytes(v for row in grouped for v in [len(row),*[x for pair in row for x in pair]])
                (folder/'stimulus.bin').write_bytes(payload)
                subprocess.run(['.deps/cc65/bin/ca65','-g','-D',f'SOURCE_FRAMES={len(grouped)}',
                    '--bin-include-dir',str(folder),'-o',str(folder/'player.o'),'snes/nes_apu_stimulus.asm'],check=True)
                subprocess.run(['.deps/cc65/bin/ld65','-C','snes/nes_disabled_reload.cfg',
                    '-Ln',str(folder/'player.lbl'),'-o',str(folder/'player.nes'),str(folder/'player.o')],check=True)
                rom=folder/'player.nes'
                paths += [Path('snes/nes_apu_stimulus.asm'),Path('snes/nes_disabled_reload.cfg'),folder/'stimulus.bin']
            else:
                payload=b''.join(b'\1'+p for p in packets)
                if len(payload)>65535:raise ValueError('Stream too large')
                (folder/'stream.bin').write_bytes(payload);(folder/'engine.bin').write_bytes(engine)
                subprocess.run(['.deps/cc65/bin/ca65','-g','-I','snes','-D',f'SOURCE_FRAMES={len(packets)}',
                    '-D',f'SWEEP_DRIVER_BYTES={len(engine)}','-D','EXPERIMENTAL_SWEEP_EVENTS=1',
                    '-D','AUDIO_PAIR=1','-D','AUDIO_FAST_RESET=1','-o',str(folder/'player.o'),
                    'snes/apu_packet_replay.asm'],check=True)
                subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-Ln',str(folder/'player.lbl'),
                    '-o',str(folder/'player.bin'),str(folder/'player.o')],check=True)
                image=bytearray(0x200000)
                image[0x8000:0x10000]=(folder/'player.bin').read_bytes()
                image[0x120000:0x120000+len(engine)]=engine
                image[0x130000:0x130000+len(payload)]=payload
                checksum(image);rom=folder/'player.sfc';rom.write_bytes(image)
                paths += [Path('snes')/name for name in ('apu_packet_replay.asm','native_boot.cfg',
                    'native_audio.asm','native_spc_frame.inc','wram_clear.inc')]
                paths += [folder/'stream.bin',folder/'engine.bin',Path('tools/build_inline_pitch_trial.py')]
            result=dict(source_frames=len(grouped),packets=len(packets),cases=cases,variant=variant,
                system=system,rom_sha256=sha(rom),source_rom_sha256=meta['rom_sha256'],
                spc_sha256=meta['spc_sha256'] if system=='snes' else None,scope=__doc__,release_ready=False,
                sources={str(p):sha(p) for p in [*paths,rom]})
            (folder/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),cases=8,periodic_resets=24,frames=len(grouped))))


def capture_nes(fixture,core,out):
    from tools.audit_main_display_latency import bound_report
    import shutil
    spec=bound_report(fixture/'manifest.json')
    if spec['system']!='nes' or out.exists():raise ValueError('Fresh NES capture required')
    grouped,_,_=stimulus(spec['variant']=='suppressed')
    expected=bytes(v for row in grouped for v in [len(row),*[x for pair in row for x in pair]])
    if expected!=(fixture/'stimulus.bin').read_bytes():raise ValueError('Different NES stimulus')
    out.mkdir(parents=True)
    for name in ('player.nes','stimulus.bin'):
        shutil.copyfile(fixture/name,out/name)
    capture_player(core,out/'player.nes',out,grouped)
    paths=[Path(__file__),Path('tools/replay_nes_apu_stimulus.py'),Path('tools/smoke_libretro.py'),
        core,fixture/'manifest.json',fixture/'player.nes',fixture/'stimulus.bin']
    paths += [out/name for name in ('player.nes','stimulus.bin','audio.wav','timeline.json','receipt.json','memory.ram')]
    result=dict(passed=True,source_frames=len(grouped),cases=spec['cases'],variant=spec['variant'],
        writes=sum(map(len,grouped)),scope='Synthetic pulse-2 reference; every executed frame, write count and shadow checked; native audio retained.',
        sources={str(p):sha(p) for p in paths})
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    b=sub.add_parser('build')
    for name in ('candidate','out'):b.add_argument('--'+name,type=Path,required=True)
    c=sub.add_parser('capture-nes')
    for name in ('fixture','core','out'):c.add_argument('--'+name,type=Path,required=True)
    args=vars(p.parse_args());mode=args.pop('mode')
    (build if mode=='build' else capture_nes)(**args)
