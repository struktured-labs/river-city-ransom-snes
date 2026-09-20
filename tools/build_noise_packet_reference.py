"""Execute a noise-only NES reference from strictly limited physical packet states.

Not a recovery of original APU writes: cold LFSR, synthetic initial length load,
one snapshot per VBlank, and no original sub-frame timing. Only constant-volume,
length-halted, continuously enabled long-mode noise without DMC is supported.
"""
import argparse
import json
from pathlib import Path
import subprocess

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.replay_nes_apu_stimulus import capture_player


def stimulus(stream):
    if not stream or len(stream) % 24:
        raise ValueError('Need complete one-packet frames')
    grouped = []
    for at in range(0, len(stream), 24):
        p = stream[at+1:at+24]
        if stream[at] != 1:
            raise ValueError('Missing or multiple packets per frame')
        if p[12] & 0xf0 != 0x30 or p[14] & 0x80 or p[15] != 0:
            raise ValueError('Unsupported envelope, length or short-noise state')
        if not p[21] & 8 or p[21] & 16 or any(p[16:20]):
            raise ValueError('Need continuously enabled noise without DMC')
        # $400D is unused. Preserve $400E ignored bits rather than canonicalizing
        # the input bytes. Repeated C/E writes do not reset the noise shift register.
        writes = [(0x0c, p[12]), (0x0e, p[14])]
        if at == 0:
            writes = [(0x17, 0x40), (0x15, 8)] + writes + [(0x0f, 0)]
        grouped.append(writes)
    return grouped


def dead_store(rom):
    # Keep shadow/count instrumentation and instruction lengths unchanged while
    # directing physical writes away from the APU. An executed acoustic control.
    pattern = bytes.fromhex('9d00409d2002')
    if rom.count(pattern) != 1:
        raise ValueError('Ambiguous NES physical-store preimage')
    at = rom.index(pattern)
    result = bytearray(rom)
    result[at+2] = 0x50
    return bytes(result)


def run(fixture, hardware, core, out):
    if out.exists():
        raise ValueError('Fresh output required')
    spec = bound_report(fixture/'manifest.json')
    physical = bound_report(hardware/'report.json')
    stream = (fixture/'stream.bin').read_bytes()
    if (spec['source_rom_sha256'] != physical['diagnostic_rom_sha256'] or
            stream != b''.join(b'\1'+bytes.fromhex(r['packet']) for r in physical['log']['records'])):
        raise ValueError('Different physical packet episode')
    grouped = stimulus(stream)
    if len(grouped) != spec['source_frames']:
        raise ValueError('Different frame coverage')
    payload = bytes(v for row in grouped for v in [len(row), *[v for pair in row for v in pair]])
    if len(payload) > 32000:
        raise ValueError('NROM stimulus capacity exceeded')
    out.mkdir(parents=True)
    (out/'stimulus.bin').write_bytes(payload)
    subprocess.run(['.deps/cc65/bin/ca65', '-g', '-D', f'SOURCE_FRAMES={len(grouped)}',
        '--bin-include-dir', str(out), '-o', str(out/'player.o'), 'snes/nes_apu_stimulus.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/nes_disabled_reload.cfg',
        '-o', str(out/'player.nes'), str(out/'player.o')], check=True)
    capture_player(core, out/'player.nes', out, grouped)
    control = out/'dead-store'; control.mkdir()
    (control/'player.nes').write_bytes(dead_store((out/'player.nes').read_bytes()))
    try:
        capture_player(core, control/'player.nes', control, grouped)
    except ValueError as error:
        if str(error) != 'Executed stimulus is silent':
            raise
        rejected = str(error)
    else:
        raise ValueError('Dead physical-store mutation escaped detection')
    paths = [Path(__file__), Path('tools/replay_nes_apu_stimulus.py'), Path('tools/smoke_libretro.py'),
        Path('snes/nes_apu_stimulus.asm'), Path('snes/nes_disabled_reload.cfg'),
        Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65'), core,
        fixture/'manifest.json', fixture/'stream.bin', hardware/'report.json']
    paths += [out/n for n in ('stimulus.bin','player.nes','audio.wav','timeline.json','receipt.json','memory.ram')]
    paths += [control/'player.nes', control/'audio.wav']
    report = dict(passed=True, source_frames=len(grouped), writes=sum(map(len, grouped)),
        physical_packets=len(grouped), source_spc_sha256=spec['spc_sha256'],
        executed_negative_control=rejected, original_write_reconstruction=False,
        physical_causality_proven=False, release_ready=False, scope=__doc__,
        sources={str(p):sha(p) for p in paths})
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='sources'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','hardware','core','out'):
        parser.add_argument('--'+name, type=Path, required=True)
    run(**vars(parser.parse_args()))
