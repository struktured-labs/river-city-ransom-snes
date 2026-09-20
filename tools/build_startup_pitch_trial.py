"""Offline restart-only pitch staging during DSP startup; no game promotion."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_sweep_kernel import Program

ENGINE_SHA = 'c880c1c1c5174305a8a8256809c55d4b6dc44cd21237b019eace5dc902c28a76'
ORIGIN = 0x3500
VALID = 0x35f0
BYTES = 0x3200


def helpers(delay=16):
    if not 1 <= delay <= 255:
        raise ValueError('Invalid bounded startup delay')
    p = Program(ORIGIN)
    for voice in (0, 1):
        p.label(f'stage{voice}')
        p.put(0xe4, 0x54, 0x28, 1 << voice)
        p.when(0xf0, f'ordinary{voice}')
        address = VALID+1+2*voice
        # X/Y hold prefetched low/high pitch. No emulated timer or port polling
        # can interleave this synchronous publication and the following flush.
        p.put(0xc9, address & 255, address >> 8,
              0xcc, (address+1) & 255, (address+1) >> 8,
              0xe5, VALID & 255, VALID >> 8, 0x08, 1 << voice,
              0xc5, VALID & 255, VALID >> 8, 0x6f)
        p.label(f'ordinary{voice}')
        # A was used to inspect the mask; restore the high-register address.
        p.put(0xe8, voice*16+3, 0x8f, voice*16+2, 0xf2, 0xd8, 0xf3, 0xda, 0xf2, 0x6f)
    p.label('flush')
    p.put(0xe4, 0x54)
    p.when(0xf0, 'finish')
    p.put(0x8f, 0x4c, 0xf2, 0xc4, 0xf3)
    # Executed clock checks must establish the safe startup window. Sixteen
    # iterations nominally take96 clocks; no wall-clock/CPU epoch assumption.
    p.put(0xcd, delay, 0x1d, 0xd0, 0xfd)
    for voice in (0, 1):
        address = VALID+1+2*voice
        p.put(0xe5, VALID & 255, VALID >> 8, 0x28, 1 << voice)
        p.when(0xf0, f'skip{voice}')
        p.put(0x8f, voice*16+2, 0xf2,
              0xe5, address & 255, address >> 8, 0xc4, 0xf3,
              0xe5, (address+1) & 255, (address+1) >> 8,
              0xab, 0xf2, 0xc4, 0xf3)
        p.label(f'skip{voice}')
    p.label('finish')
    p.put(0xe8, 0, 0xc5, VALID & 255, VALID >> 8,
          0x8f, 0, 0x54, 0x8f, 0x7d, 0xf4, 0x6f)
    code, labels = p.result()
    if ORIGIN+len(code) > VALID:
        raise ValueError('Helper overlaps staged pitch storage')
    return code, labels


def patch(engine, layout, delay=16):
    if len(engine) != 12415 or hashlib.sha256(engine).hexdigest() != ENGINE_SHA:
        raise ValueError('Need exact current SPC engine')
    code, labels = helpers(delay)
    baseline = engine+bytes(BYTES-len(engine))
    trial = bytearray(baseline)
    changes = []
    for voice in (0, 1):
        at = layout['driver'][f'publish{voice}_audible']-0x400+33
        old = bytes((0x8f, voice*16+2, 0xf2, 0xd8, 0xf3, 0xda, 0xf2))
        target = labels[f'stage{voice}']
        new = bytes((0x3f, target & 255, target >> 8))+bytes(4)
        if engine[at:at+7] != old:
            raise ValueError('Word-pitch tail differs')
        trial[at:at+7] = new
        changes.append(dict(offset=at, before=old.hex(), after=new.hex()))
    at = 0x2b80
    old = bytes.fromhex('e454f0068f4cf2c4f3008f00548f7df46f')
    if engine[at:at+len(old)] != old:
        raise ValueError('Postpublication helper differs')
    target = labels['flush']
    trial[at:at+3] = bytes((0x5f, target & 255, target >> 8))
    changes.append(dict(offset=at, before=old[:3].hex(), after=bytes(trial[at:at+3]).hex()))
    trial[ORIGIN-0x400:ORIGIN-0x400+len(code)] = code
    return baseline, bytes(trial), dict(labels=labels, helper_hex=code.hex(),
        delay_iterations=delay, storage_address=VALID, storage_bytes=5,
        changes=changes, original_engine_bytes=len(engine), engine_bytes=BYTES,
        scope=__doc__, release_ready=False)


def build(fixture, candidate, out):
    if out.exists():
        raise ValueError('Fresh fixtures required')
    spec = bound_report(fixture/'manifest.json')
    game = json.loads((candidate/'manifest.json').read_text())
    if sha(candidate/'native-cpu.sfc') != game['rom_sha256']:
        raise ValueError('Unbound game')
    engine = (fixture/'engine.bin').read_bytes()
    if sha(fixture/'engine.bin') != game['spc_sha256']:
        raise ValueError('Fixture has different engine')
    baseline, trial, detail = patch(engine, game['sweep_driver_layout'])
    stream = (fixture/'stream.bin').read_bytes()
    out.mkdir()
    for name, content in [('baseline', baseline), ('trial', trial)]:
        folder = out/name; folder.mkdir()
        (folder/'engine.bin').write_bytes(content)
        (folder/'stream.bin').write_bytes(stream)
        subprocess.run(['.deps/cc65/bin/ca65', '-g', '-I', 'snes', '-D', f'SOURCE_FRAMES={spec["source_frames"]}',
            '-D', f'SWEEP_DRIVER_BYTES={len(content)}', '-D', 'EXPERIMENTAL_SWEEP_EVENTS=1',
            '-D', 'AUDIO_PAIR=1', '-D', 'AUDIO_FAST_RESET=1', '-o', str(folder/'player.o'),
            'snes/apu_packet_replay.asm'], check=True)
        subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/native_boot.cfg', '-Ln', str(folder/'player.lbl'),
                        '-o', str(folder/'player.bin'), str(folder/'player.o')], check=True)
        image = bytearray(0x200000)
        image[0x8000:0x10000] = (folder/'player.bin').read_bytes()
        image[0x120000:0x120000+len(content)] = content
        image[0x130000:0x130000+len(stream)] = stream
        checksum(image); (folder/'player.sfc').write_bytes(image)
        paths = [Path(__file__), Path('tests/test_startup_pitch.py'), Path('tools/build_sweep_kernel.py'),
                 Path('tools/build_inline_pitch_trial.py'), fixture/'manifest.json', fixture/'engine.bin',
                 fixture/'stream.bin', candidate/'manifest.json', candidate/'native-cpu.sfc',
                 Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65')]
        paths += [Path('snes')/n for n in ('apu_packet_replay.asm', 'native_boot.cfg',
                                          'native_audio.asm', 'native_spc_frame.inc', 'wram_clear.inc')]
        paths += [folder/n for n in ('player.sfc', 'engine.bin', 'stream.bin')]
        manifest = dict(spec, mutation='startup-pitch-'+name, startup_pitch=detail,
            rom_sha256=sha(folder/'player.sfc'), spc_sha256=sha(folder/'engine.bin'),
            engine_source_rom_sha256=game['rom_sha256'], scope=__doc__, release_ready=False,
            sources={str(p): sha(p) for p in paths})
        (folder/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(detail))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('fixture', 'candidate', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    build(**vars(parser.parse_args()))
