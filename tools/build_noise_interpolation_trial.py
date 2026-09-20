"""Controlled 2x/8x BRR bit-hold experiments, not production noise synthesis.

Both arms loop the SAME first8192 bits of the long LFSR, not its full32767-bit
cycle. Fixed upload size, code, level and fast-rate fallback. Only sample hold
and matching pitch differ. The shortened loop prohibits release promotion.
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


def sample(repeats):
    if repeats not in (2, 8):
        raise ValueError('Only paired 2x/8x controls')
    state = 1
    values = []
    for _ in range(8192):
        values.extend([-7 if state & 1 else 7]*repeats)
        state = (state >> 1) | (((state ^ (state >> 1)) & 1) << 14)
    blocks = bytearray()
    for at in range(0, len(values), 16):
        blocks.append(0xc3 if at+16 == len(values) else 0xc0)
        blocks.extend(((a & 15) << 4) | (b & 15)
                      for a, b in zip(values[at:at+16:2], values[at+1:at+16:2]))
    return bytes(blocks), state


def patch(engine, repeats):
    base, _ = base_patch(engine)
    data, next_state = sample(repeats)
    # Constant upload duration between both arms, including unused zero padding.
    result = bytearray(base[:0x3c00])+bytearray(36864)
    result[0x3c00:0x3c00+len(data)] = data
    fast = bytes.fromhex('8f3df28f08f3f5c0358f6cf2c4f36f')
    slow = bytes.fromhex('8f3df28f00f3f5b0352df5a035ce8f32f2c4f3abf2d8f36f')
    helper = bytes((0xc8, 6, 0xb0, len(fast)))+fast+slow
    result[0x3120:0x3120+len(helper)] = helper
    pitches = [0 if i < 6 else round(1789773/p/32000*4096*repeats)
               for i, p in enumerate(NES_NOISE_PERIODS)]
    if any(p > 16383 for p in pitches) or len(result)+0x400 > 0xffc0:
        raise ValueError('Pitch or SPC memory overflow')
    result[0x31a0:0x31b0] = bytes(p & 255 for p in pitches)
    result[0x31b0:0x31c0] = bytes(p >> 8 for p in pitches)
    result[0x31c0:0x31d0] = engine[0x849:0x859]
    return bytes(result), dict(level=7, repeats_per_bit=repeats, states=8192,
        loop_samples=8192*repeats, full_lfsr_cycle=False, next_unplayed_lfsr_state=next_state,
        sample_bytes=len(data), reserved_sample_bytes=36864, sample_spc_address=0x4000,
        fallback_rates=list(range(6)), pitches=pitches, helper=helper.hex(), scope=__doc__)


def build(fixture, repeats, out):
    if out.exists():
        raise ValueError('Fresh fixture required')
    spec = bound_report(fixture/'manifest.json')
    stream = (fixture/'stream.bin').read_bytes()
    if len(stream) != spec['source_frames']*24 or any(
            stream[i] != 1 or stream[i+15] & 128 for i in range(0, len(stream), 24)):
        raise ValueError('Need one long-mode diagnostic packet per frame')
    engine, detail = patch((fixture/'engine.bin').read_bytes(), repeats)
    out.mkdir(parents=True)
    (out/'engine.bin').write_bytes(engine)
    (out/'stream.bin').write_bytes(stream)
    subprocess.run(['.deps/cc65/bin/ca65','-g','-I','snes','-D',f'SOURCE_FRAMES={spec["source_frames"]}',
        '-D',f'SWEEP_DRIVER_BYTES={len(engine)}','-D','EXPERIMENTAL_SWEEP_EVENTS=1',
        '-D','AUDIO_PAIR=1','-D','AUDIO_FAST_RESET=1','-o',str(out/'player.o'),'snes/apu_packet_replay.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-o',str(out/'player.bin'),str(out/'player.o')],check=True)
    image = bytearray(0x200000)
    image[0x8000:0x10000] = (out/'player.bin').read_bytes()
    image[0x120000:0x120000+len(engine)] = engine
    image[0x130000:0x130000+len(stream)] = stream
    checksum(image)
    (out/'player.sfc').write_bytes(image)
    paths = [Path(__file__), Path('tools/build_brr_noise_replay.py'),
        Path('tools/build_inline_pitch_trial.py'), Path('tools/prepare_audio.py'),
        fixture/'manifest.json', fixture/'engine.bin', fixture/'stream.bin',
        Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65')]
    paths += [Path('snes')/n for n in ('apu_packet_replay.asm','native_boot.cfg',
                                     'native_audio.asm','native_spc_frame.inc','wram_clear.inc')]
    paths += [out/n for n in ('player.sfc','engine.bin','stream.bin')]
    result = dict(spec, rom_sha256=sha(out/'player.sfc'), spc_sha256=sha(out/'engine.bin'),
        mutation=f'noise-interpolation-{repeats}x-short-loop', noise_prototype=detail,
        release_ready=False, sources={str(p):sha(p) for p in paths})
    (out/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), engine_bytes=len(engine), **detail)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('fixture', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--repeats', type=int, choices=(2,8), required=True)
    build(**vars(p.parse_args()))
