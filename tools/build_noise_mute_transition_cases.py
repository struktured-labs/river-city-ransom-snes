"""Execute source-changing zero-volume commands, not just channel disable."""
import argparse
import json
from pathlib import Path
import subprocess

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_noise_level_reference import stimulus as held_stimulus


def stimulus():
    _, held, _ = held_stimulus()
    packets = held[:144]  # Two original pulse-level/restart controls.
    cases = []
    for period,volume,frames in ((6,15,16),(2,0,8),(2,15,16),(6,0,8),(6,15,16)):
        first = len(packets)+1
        p = bytearray(23)
        p[12],p[14],p[21] = 0x30|volume,period,8
        packets.extend([bytes(p)]*frames)
        cases.append(dict(first_frame=first,last_frame=len(packets),period=period,
                          volume=volume,enabled=8))
    packets.extend([bytes(23)]*60)
    return packets,cases


def build(fixture,out):
    if out.exists():
        raise ValueError('Fresh diagnostic required')
    spec = bound_report(fixture/'manifest.json')
    if not spec.get('source_first') or spec['noise_prototype']['repeats_per_bit'] != 8:
        raise ValueError('Need source-first 8x fixture')
    engine = (fixture/'engine.bin').read_bytes()
    packets,cases = stimulus()
    stream = b''.join(b'\1'+p for p in packets)
    out.mkdir(parents=True)
    (out/'engine.bin').write_bytes(engine); (out/'stream.bin').write_bytes(stream)
    subprocess.run(['.deps/cc65/bin/ca65','-g','-I','snes','-D',f'SOURCE_FRAMES={len(packets)}',
        '-D',f'SWEEP_DRIVER_BYTES={len(engine)}','-D','EXPERIMENTAL_SWEEP_EVENTS=1',
        '-D','AUDIO_PAIR=1','-D','AUDIO_FAST_RESET=1','-o',str(out/'player.o'),'snes/apu_packet_replay.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-o',str(out/'player.bin'),str(out/'player.o')],check=True)
    image = bytearray(0x200000)
    image[0x8000:0x10000] = (out/'player.bin').read_bytes()
    image[0x120000:0x120000+len(engine)] = engine
    image[0x130000:0x130000+len(stream)] = stream
    checksum(image); (out/'player.sfc').write_bytes(image)
    paths = [Path(__file__),Path('tools/build_noise_level_reference.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),fixture/'manifest.json',fixture/'engine.bin']
    paths += [Path('snes')/n for n in ('apu_packet_replay.asm','native_boot.cfg','native_audio.asm','native_spc_frame.inc','wram_clear.inc')]
    paths += [out/n for n in ('player.sfc','engine.bin','stream.bin')]
    report = dict(spec,source_frames=len(packets),packets=len(packets),cases=cases,
        rom_sha256=sha(out/'player.sfc'),spc_sha256=sha(out/'engine.bin'),
        mutation='enabled-zero-volume-source-transitions',scope=__doc__,release_ready=False,
        sources={str(p):sha(p) for p in paths})
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),frames=len(packets),cases=cases)))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
