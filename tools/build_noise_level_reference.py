"""Isolated noise rates2..15 at volumes4/15, with pulse-level controls.

Fixed64-frame held cases separated by eight muted frames; final60-frame mute.
Same state schedule on NES and both SPC engines. Not a gameplay or analog oracle.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.capture_noise_quality_reference import quality_options
from tools.replay_nes_apu_stimulus import capture_player


def stimulus():
    grouped=[];packets=[];cases=[]
    for channel in ('pulse','noise'):
        for volume in (4,15):
            for period in ((253,) if channel=='pulse' else range(2,16)):
                first=len(grouped)+1
                for frame in range(64):
                    p=bytearray(23);writes=[]
                    if channel=='pulse':
                        p[:4]=bytes((0xb0|volume,8,period,0));p[21]=1
                        if frame==0:
                            p[20],p[22]=0x1c,1
                            writes=[(0x15,1),(0,0xb0|volume),(1,8),(2,period),(3,0)]
                    else:
                        p[12],p[14],p[21]=0x30|volume,period,8
                        if frame==0:writes=[(0x15,8),(12,0x30|volume),(14,period),(15,0)]
                    if not grouped:writes=[(0x17,0x40)]+writes
                    grouped.append(writes);packets.append(bytes(p))
                cases.append(dict(channel=channel,volume=volume,period=period,first_frame=first,last_frame=len(grouped)))
                for frame in range(8):
                    grouped.append([(0x15,0)] if frame==0 else []);packets.append(bytes(23))
    for _ in range(60):grouped.append([]);packets.append(bytes(23))
    return grouped,packets,cases


def build(parent,trial,out):
    if out.exists():raise ValueError('Fresh fixture required')
    specs=[bound_report(p/'manifest.json') for p in (parent,trial)]
    grouped,packets,cases=stimulus();out.mkdir(parents=True)
    stream=b''.join(b'\1'+p for p in packets)
    if len(stream)>65535:raise ValueError('Single-bank capacity exceeded')
    for system in ('nes','parent','trial'):
        folder=out/system;folder.mkdir()
        paths=[Path(__file__),parent/'manifest.json',trial/'manifest.json',
            Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65')]
        if system=='nes':
            payload=bytes(v for row in grouped for v in [len(row),*[v for pair in row for v in pair]])
            (folder/'stimulus.bin').write_bytes(payload)
            subprocess.run(['.deps/cc65/bin/ca65','-g','-D',f'SOURCE_FRAMES={len(grouped)}',
                '--bin-include-dir',str(folder),'-o',str(folder/'player.o'),'snes/nes_apu_stimulus.asm'],check=True)
            subprocess.run(['.deps/cc65/bin/ld65','-C','snes/nes_disabled_reload.cfg',
                '-o',str(folder/'player.nes'),str(folder/'player.o')],check=True)
            paths += [Path('snes/nes_apu_stimulus.asm'),Path('snes/nes_disabled_reload.cfg'),folder/'player.nes',folder/'stimulus.bin']
        else:
            source=parent if system=='parent' else trial;engine=(source/'engine.bin').read_bytes()
            (folder/'engine.bin').write_bytes(engine);(folder/'stream.bin').write_bytes(stream)
            subprocess.run(['.deps/cc65/bin/ca65','-g','-I','snes','-D',f'SOURCE_FRAMES={len(packets)}',
                '-D',f'SWEEP_DRIVER_BYTES={len(engine)}','-D','EXPERIMENTAL_SWEEP_EVENTS=1',
                '-D','AUDIO_PAIR=1','-D','AUDIO_FAST_RESET=1','-o',str(folder/'player.o'),'snes/apu_packet_replay.asm'],check=True)
            subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-o',str(folder/'player.bin'),str(folder/'player.o')],check=True)
            image=bytearray(0x200000);image[0x8000:0x10000]=(folder/'player.bin').read_bytes()
            image[0x120000:0x120000+len(engine)]=engine;image[0x130000:0x130000+len(stream)]=stream
            checksum(image);(folder/'player.sfc').write_bytes(image)
            paths += [source/'engine.bin',folder/'engine.bin',folder/'stream.bin',folder/'player.sfc',Path('tools/build_inline_pitch_trial.py')]
            paths += [Path('snes')/n for n in ('apu_packet_replay.asm','native_boot.cfg','native_audio.asm','native_spc_frame.inc','wram_clear.inc')]
        report=dict(source_frames=len(grouped),packets=len(packets),cases=cases,system=system,
            rom_sha256=sha(folder/('player.nes' if system=='nes' else 'player.sfc')),
            spc_sha256=None if system=='nes' else sha(folder/'engine.bin'),
            scope=__doc__,release_ready=False,sources={str(p):sha(p) for p in paths})
        (folder/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(frames=len(grouped),cases=len(cases),out=str(out))))


def capture_nes(fixture,core,out,observe=False):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):raise ValueError('Fresh output/clean observer environment required')
    spec=bound_report(fixture/'manifest.json');grouped,_,cases=stimulus()
    if spec['system']!='nes' or spec['cases']!=cases or spec['source_frames']!=len(grouped):raise ValueError('Different schedule')
    expected=bytes(v for row in grouped for v in [len(row),*[v for pair in row for v in pair]])
    if expected!=(fixture/'stimulus.bin').read_bytes():raise ValueError('Different NES state writes')
    out.mkdir(parents=True)
    for n in ('player.nes','stimulus.bin'):shutil.copyfile(fixture/n,out/n)
    traces={}
    if observe:
        traces=dict(samples=str(out/'filter.pcm'),blocks=str(out/'filter.csv'))
        os.environ.update(RCR_NES_FILTER_PCM=str((out/'filter.pcm').resolve()),RCR_NES_FILTER_BLOCKS=str((out/'filter.csv').resolve()))
    try:
        with quality_options('Very High') as queries:capture_player(core,out/'player.nes',out,grouped)
    finally:
        os.environ.pop('RCR_NES_FILTER_PCM',None);os.environ.pop('RCR_NES_FILTER_BLOCKS',None)
    paths=[Path(__file__),Path('tools/capture_noise_quality_reference.py'),Path('tools/replay_nes_apu_stimulus.py'),
        Path('tools/smoke_libretro.py'),Path('tools/fceumm_filter_observer.inc'),core,fixture/'manifest.json',fixture/'player.nes',fixture/'stimulus.bin']
    paths += [out/n for n in ('audio.wav','timeline.json','receipt.json','memory.ram','player.nes','stimulus.bin')]
    report=dict(passed=True,source_frames=len(grouped),cases=cases,options_queried=queries,traces=traces,
        scope='Held diagnostic signals; native Very High NES output, no phase/gain fitting.',release_ready=False,sources={str(p):sha(p) for p in paths})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='mode',required=True)
    b=s.add_parser('build')
    for n in ('parent','trial','out'):b.add_argument('--'+n,type=Path,required=True)
    c=s.add_parser('capture-nes')
    for n in ('fixture','core','out'):c.add_argument('--'+n,type=Path,required=True)
    c.add_argument('--observe',action='store_true')
    args=vars(p.parse_args());mode=args.pop('mode')
    (build if mode=='build' else capture_nes)(**args)
