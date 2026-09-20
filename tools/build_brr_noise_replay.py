"""Offline long-noise BRR prototype on the current SPC command replay.

NES binary LFSR instead of the DSP's signed multilevel noise. Rates2..15 only;
no short mode. A full32767-state cycle gains one held sample for BRR alignment.
That seam, Gaussian interpolation, pitch quantization and source-state timing
are explicit approximations. Not a production cartridge or hardware release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_noise_packet_reference import stimulus
from tools.prepare_audio import NES_NOISE_PERIODS


def noise_sample():
    state=1;states=set();levels=[]
    while state not in states:
        states.add(state);levels.append(-4 if state&1 else 4)
        state=(state>>1)|(((state^(state>>1))&1)<<14)
    if len(states)!=32767 or state!=1:raise ValueError('Incorrect full noise cycle')
    levels.append(levels[-1])  # explicit single held sample, never hidden padding
    blocks=bytearray()
    for at in range(0,len(levels),16):
        block=levels[at:at+16]
        blocks.append(0xc3 if at+16==len(levels) else 0xc0)
        blocks.extend(((a&15)<<4)|(b&15) for a,b in zip(block[::2],block[1::2]))
    return bytes(blocks)


def patch(engine):
    if len(engine)!=12415 or hashlib.sha256(engine).hexdigest()!= 'c880c1c1c5174305a8a8256809c55d4b6dc44cd21237b019eace5dc902c28a76':
        raise ValueError('Need exact current SPC engine')
    sample=noise_sample();result=bytearray(engine)+bytearray(0x3c00+len(sample)-len(engine))
    changes=[]
    def replace(at,old,new):
        if len(old)!=len(new) or result[at:at+len(old)]!=old:raise ValueError('Changed SPC preimage')
        result[at:at+len(old)]=new;changes.append(dict(offset=at,before=old.hex(),after=new.hex()))
    replace(0x4a,bytes.fromhex('8f34f28f00f3'),bytes.fromhex('8f34f28f05f3'))
    replace(0x68,bytes.fromhex('8f3df28f08f3'),bytes.fromhex('8f3df28f00f3'))
    # Last directory RET plus two now-unused clock-table bytes become JMP $3500.
    replace(0x848,bytes.fromhex('6f3f3f'),bytes.fromhex('5f0035'))
    replace(0x332,bytes.fromhex('f5490c8f6cf2c4f3'),bytes.fromhex('3f20350000000000'))
    directory=bytes.fromhex('e800c51402c51602e840c51502c517026f')
    result[0x3100:0x3100+len(directory)]=directory
    # Prefetch both pitch bytes before selecting DSP pitch-low, then use the
    # existing pulse publisher's low/inc-F2/high sequence. X is scratch here.
    helper=bytes.fromhex('f5b0352df5a035ce8f32f2c4f3abf2d8f36f')
    result[0x3120:0x3120+len(helper)]=helper
    pitches=[min(16383,round(1789773/p/32000*4096)) for p in NES_NOISE_PERIODS]
    result[0x31a0:0x31b0]=bytes(p&255 for p in pitches)
    result[0x31b0:0x31c0]=bytes(p>>8 for p in pitches)
    result[0x3c00:]=sample
    return bytes(result),dict(changes=changes,pitches=pitches,sample_spc_address=0x4000,
        sample_bytes=len(sample),lfsr_states=32767,loop_samples=32768,inserted_hold_samples=1,
        unsupported_rates=[0,1],source_number=5,scope=__doc__)


def build(fixture,out):
    if out.exists():raise ValueError('Fresh offline fixture required')
    original=bound_report(fixture/'manifest.json');stream=(fixture/'stream.bin').read_bytes()
    stimulus(stream)  # fail closed for envelope/short-mode/DMC/enable states
    if any((stream[i+15]&15)<2 for i in range(0,len(stream),24)):
        raise ValueError('Fast noise rates0/1 cannot use this single BRR cycle')
    engine,detail=patch((fixture/'engine.bin').read_bytes())
    out.mkdir(parents=True)
    (out/'engine.bin').write_bytes(engine);(out/'stream.bin').write_bytes(stream)
    subprocess.run(['.deps/cc65/bin/ca65','-g','-I','snes','-D',f'SOURCE_FRAMES={original["source_frames"]}',
        '-D',f'SWEEP_DRIVER_BYTES={len(engine)}','-D','EXPERIMENTAL_SWEEP_EVENTS=1',
        '-D','AUDIO_PAIR=1','-D','AUDIO_FAST_RESET=1','-o',str(out/'player.o'),'snes/apu_packet_replay.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-Ln',str(out/'player.lbl'),
        '-o',str(out/'player.bin'),str(out/'player.o')],check=True)
    image=bytearray(0x200000);image[0x8000:0x10000]=(out/'player.bin').read_bytes()
    image[0x120000:0x120000+len(engine)]=engine;image[0x130000:0x130000+len(stream)]=stream
    checksum(image);(out/'player.sfc').write_bytes(image)
    paths=[Path(__file__),Path('tools/build_noise_packet_reference.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('tools/prepare_audio.py'),fixture/'manifest.json',fixture/'engine.bin',fixture/'stream.bin',
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65')]
    paths += [Path('snes')/n for n in ('apu_packet_replay.asm','native_boot.cfg','native_audio.asm','native_spc_frame.inc','wram_clear.inc')]
    paths += [out/n for n in ('engine.bin','stream.bin','player.sfc')]
    manifest=dict(source_frames=original['source_frames'],packets=original['packets'],
        rom_sha256=sha(out/'player.sfc'),spc_sha256=sha(out/'engine.bin'),mutation='binary-long-noise-BRR',
        source_rom_sha256=original['source_rom_sha256'],initial_spc_state='cold',
        noise_prototype=detail,sources={str(p):sha(p) for p in paths},release_ready=False,
        scope=__doc__)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),engine_bytes=len(engine),**detail)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
