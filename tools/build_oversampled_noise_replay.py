"""Offline 2x full-cycle BRR noise with explicit fast-rate DSP fallback.

All32767 long-LFSR states retained, each held for two samples, then two padding
samples. Rates0..2 retain built-in DSP noise;3..15 use doubled BRR pitch. Short
mode unsupported. Neither the hybrid transition nor the loop seam is qualified.
"""
import argparse
import json
from pathlib import Path
import subprocess

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_brr_noise_replay import patch as base_patch
from tools.build_inline_pitch_trial import checksum
from tools.prepare_audio import NES_NOISE_PERIODS


def sample(level):
    if level not in (4,7):raise ValueError('Only declared amplitude-control variants')
    state=1;seen=set();values=[]
    while state not in seen:
        seen.add(state);value=-level if state&1 else level;values.extend((value,value))
        state=(state>>1)|(((state^(state>>1))&1)<<14)
    if len(seen)!=32767 or state!=1:raise ValueError('Wrong LFSR period')
    values.extend((values[-1],values[-1]))
    brr=bytearray()
    for at in range(0,len(values),16):
        brr.append(0xc3 if at+16==len(values) else 0xc0)
        brr.extend(((a&15)<<4)|(b&15) for a,b in zip(values[at:at+16:2],values[at+1:at+16:2]))
    return bytes(brr)


def patch(engine,level):
    base,_=base_patch(engine)  # exact current engine/hash and preimages
    result=bytearray(base[:0x3c00])+bytearray(sample(level))
    if len(result)+0x400>0xffc0:raise ValueError('Sample reaches IPL')
    # X is noise period index,3..15 select BRR. Fast rates keep the existing
    # clock table and NON bit rather than pretending a clipped pitch is exact.
    fast=bytes.fromhex('8f3df28f08f3f5c0358f6cf2c4f36f')
    slow=bytes.fromhex('8f3df28f00f3f5b0352df5a035ce8f32f2c4f3abf2d8f36f')
    helper=bytes((0xc8,3,0xb0,len(fast)))+fast+slow
    result[0x3120:0x3120+len(helper)]=helper
    pitches=[0 if i<3 else round(1789773/p/32000*4096*2) for i,p in enumerate(NES_NOISE_PERIODS)]
    if any(p>16383 for p in pitches):raise ValueError('Unsupported doubled pitch')
    result[0x31a0:0x31b0]=bytes(p&255 for p in pitches)
    result[0x31b0:0x31c0]=bytes(p>>8 for p in pitches)
    result[0x31c0:0x31d0]=engine[0x849:0x859]
    return bytes(result),dict(level=level,repeats_per_bit=2,states=32767,loop_samples=65536,
        padding_samples=2,sample_bytes=36864,sample_spc_address=0x4000,
        fallback_rates=[0,1,2],pitches=pitches,helper=helper.hex(),scope=__doc__)


def build(fixture,engine_source,level,out):
    if out.exists():raise ValueError('Fresh fixture required')
    spec=bound_report(fixture/'manifest.json');bound_report(engine_source/'manifest.json')
    stream=(fixture/'stream.bin').read_bytes()
    if len(stream)%24 or any(stream[i]!=1 or stream[i+15]&128 for i in range(0,len(stream),24)):
        raise ValueError('Need one long-mode packet per frame')
    engine,detail=patch((engine_source/'engine.bin').read_bytes(),level)
    out.mkdir(parents=True);(out/'engine.bin').write_bytes(engine);(out/'stream.bin').write_bytes(stream)
    subprocess.run(['.deps/cc65/bin/ca65','-g','-I','snes','-D',f'SOURCE_FRAMES={spec["source_frames"]}',
        '-D',f'SWEEP_DRIVER_BYTES={len(engine)}','-D','EXPERIMENTAL_SWEEP_EVENTS=1',
        '-D','AUDIO_PAIR=1','-D','AUDIO_FAST_RESET=1','-o',str(out/'player.o'),'snes/apu_packet_replay.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-o',str(out/'player.bin'),str(out/'player.o')],check=True)
    image=bytearray(0x200000);image[0x8000:0x10000]=(out/'player.bin').read_bytes()
    image[0x120000:0x120000+len(engine)]=engine;image[0x130000:0x130000+len(stream)]=stream
    checksum(image);(out/'player.sfc').write_bytes(image)
    paths=[Path(__file__),Path('tools/build_brr_noise_replay.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('tools/prepare_audio.py'),fixture/'manifest.json',fixture/'stream.bin',engine_source/'manifest.json',engine_source/'engine.bin',
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65')]
    paths += [Path('snes')/n for n in ('apu_packet_replay.asm','native_boot.cfg','native_audio.asm','native_spc_frame.inc','wram_clear.inc')]
    paths += [out/n for n in ('player.sfc','engine.bin','stream.bin')]
    result=dict(spec,rom_sha256=sha(out/'player.sfc'),spc_sha256=sha(out/'engine.bin'),
        mutation='2x-binary-noise-level-'+str(level),noise_prototype=detail,
        release_ready=False,sources={str(p):sha(p) for p in paths})
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),engine_bytes=len(engine),level=level)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','engine-source','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--level',type=int,choices=(4,7),required=True)
    build(**vars(p.parse_args()))
