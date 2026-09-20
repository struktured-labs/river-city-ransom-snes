"""Isolated restart-volume staging with equal-length padded controls; no deployment."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha
from tools.build_compact_startup_pitch import FINISH, FLUSH, sections
from tools.build_inline_pitch_trial import checksum
from tools.build_startup_pitch_cases import stimulus

ENGINE_SHA = 'f22ccdd429c64fc8eb0f7e830ab8183fb938f0cbc85fe75babf11b0d371e009a'
HELPERS = (0x3480, 0x348f)
LATE = 0x349e
VOLUMES = 0x34b0
ENGINE_BYTES = 0x30c0


def patch(engine, layout):
    if len(engine) != 12415 or hashlib.sha256(engine).hexdigest() != ENGINE_SHA:
        raise ValueError('Need exact phase80 sound engine')
    baseline = engine+bytes(ENGINE_BYTES-len(engine))
    data = bytearray(baseline)
    changes = []

    def replace(address, before, after):
        at = address-0x400
        if len(before) != len(after) or data[at:at+len(before)] != before:
            raise ValueError(f'Changed preimage at {address:04x}')
        data[at:at+len(after)] = after
        changes.append(dict(address=address, before=before.hex(), after=after.hex()))

    for voice, helper in enumerate(HELPERS):
        dsp = voice*16
        original = bytes((0x8f,dsp,0xf2,0xc4,0xf3,0x8f,dsp+1,0xf2,0xc4,0xf3))
        # Store every calculated volume, including muted restarts. BBC preserves
        # A. With a pending restart, return without exposing the old oscillator
        # at its new volume. Ordinary publishers still write both sides now.
        code = bytes((0x13+voice*0x20,0x54,1,0x6f))+original+bytes((0x6f,))
        replace(helper,bytes(len(code)),code)
        site = layout['driver'][f'publish{voice}_volume']
        resume = site+10
        code = bytes((0xc5,(VOLUMES+voice)&255,(VOLUMES+voice)>>8,
                      0x3f,helper&255,helper>>8,0x5f,resume&255,resume>>8,0))
        replace(site,original,code)
    # Both saved volumes are current, even when only one voice restarts. Clear
    # pending only after existing KON/pitch publication, then use the ordinary
    # writers. The second non-restarting channel merely repeats its same value.
    code = bytearray((0x8f,0,0x54))
    for voice, helper in enumerate(HELPERS):
        code.extend((0xe5,(VOLUMES+voice)&255,(VOLUMES+voice)>>8,
                     0x3f,helper&255,helper>>8))
    code.extend((0x5f,FINISH&255,FINISH>>8))
    replace(LATE,bytes(len(code)),bytes(code))
    site = FLUSH+len(sections()[FLUSH])-3
    replace(site,bytes((0x5f,FINISH&255,FINISH>>8)),bytes((0x5f,LATE&255,LATE>>8)))
    if data[0x2ba0:0x2baa] != engine[0x2ba0:0x2baa]:
        raise ValueError('Receiver helper changed')
    return baseline,bytes(data),dict(changes=changes,helpers=list(HELPERS),late=LATE,storage=VOLUMES,
        engine_bytes=len(data),original_engine_bytes=len(engine),upload_length_unchanged=False,
        equal_length_fixture_arms=True,release_ready=False,
        scope=__doc__+' Both restart volume increases and decreases are deferred; '
        'ordinary updates remain immediate. Muted restart tails must be tested, '
        'not assumed equivalent. Startup pitch timing is unchanged within flush.')


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh candidate required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Unbound parent cartridge')
    original = rom.read_bytes()
    at = meta['sweep_driver_rom_offset']
    size = meta['sweep_driver_layout']['engine_bytes']
    baseline,engine,detail = patch(original[at:at+size],meta['sweep_driver_layout'])
    packets,cases = stimulus()
    # The earlier matrix covered mute/restart and ordinary volume restoration.
    # Add a restart that unmutes an already running oscillator, the current
    # game's measured case. No game RAM or synthesis state is forced.
    for case in cases:
        index = case['first_frame']+40-1
        packet = bytearray(packets[index]); packet[20] = (12 if case['mask']&1 else 0)|(48 if case['mask']&2 else 0)
        packet[22] = case['mask']; packets[index] = bytes(packet)
    payload = b''.join(b'\1'+p for p in packets)
    if len(payload)>65535: raise ValueError('Fixture stream exceeds bank')
    out.mkdir()
    for name,content in [('baseline',baseline),('trial',engine)]:
        folder = out/name; folder.mkdir()
        (folder/'engine.bin').write_bytes(content); (folder/'stream.bin').write_bytes(payload)
        subprocess.run(['.deps/cc65/bin/ca65','-g','-I','snes','-D',f'SOURCE_FRAMES={len(packets)}',
            '-D',f'SWEEP_DRIVER_BYTES={len(content)}','-D','EXPERIMENTAL_SWEEP_EVENTS=1',
            '-D','AUDIO_PAIR=1','-D','AUDIO_FAST_RESET=1','-o',str(folder/'player.o'),
            'snes/apu_packet_replay.asm'],check=True)
        subprocess.run(['.deps/cc65/bin/ld65','-C','snes/native_boot.cfg','-Ln',str(folder/'player.lbl'),
            '-o',str(folder/'player.bin'),str(folder/'player.o')],check=True)
        image = bytearray(0x200000)
        image[0x8000:0x10000] = (folder/'player.bin').read_bytes()
        image[0x120000:0x120000+len(content)] = content
        image[0x130000:0x130000+len(payload)] = payload
        checksum(image); (folder/'player.sfc').write_bytes(image)
        paths = [Path(__file__),Path('tests/test_restart_volume_trial.py'),
            Path('tools/build_compact_startup_pitch.py'),Path('tools/build_inline_pitch_trial.py'),
            Path('tools/build_startup_pitch_cases.py'),parent/'manifest.json',rom,
            Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65')]
        paths += [Path('snes')/n for n in ('apu_packet_replay.asm','native_boot.cfg',
            'native_audio.asm','native_spc_frame.inc','wram_clear.inc')]
        paths += [folder/n for n in ('engine.bin','stream.bin','player.sfc')]
        report = dict(source_frames=len(packets),packets=len(packets),cases=cases,
            rom_sha256=sha(folder/'player.sfc'),spc_sha256=sha(folder/'engine.bin'),
            restart_volume=detail,mutation=name,release_ready=False,scope=__doc__,
            sources={str(p):sha(p) for p in paths})
        (folder/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),**detail)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'): parser.add_argument('--'+name,type=Path,required=True)
    build(**vars(parser.parse_args()))
