"""Both-voice changing-pitch, muted-restart, and resume cases for staging trial."""
import argparse
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.build_startup_pitch_trial import build as build_trial, ENGINE_SHA


def stimulus():
    packets, cases = [], []
    for old, new in ((0xfd, 0x6c6), (0xff, 0x100), (0x7ff, 8)):
        for duty in range(4):
            for mask in (1, 2, 3):
                first = len(packets)+1
                for frame in range(1, 49):
                    p = bytearray(23); p[21] = 3
                    for voice in (0, 1):
                        before, after = (old, new) if voice == 0 else (new, old)
                        period = after if mask & (1 << voice) and 17 <= frame < 33 else before
                        volume = 0 if 33 <= frame < 41 else 15
                        at = 4*voice
                        p[at:at+4] = bytes((0x30 | (duty << 6) | volume, 8, period & 255, period >> 8))
                    if frame == 1:
                        p[20], p[22] = 0x7f, 3
                    elif frame in (17, 33):
                        p[20] = (0x0c if mask & 1 else 0) | (0x30 if mask & 2 else 0)
                        p[22] = mask
                    packets.append(bytes(p))
                cases.append(dict(first_frame=first, last_frame=len(packets), old=old, new=new,
                                  duty=duty, mask=mask, changed_frame=first+16,
                                  muted_restart_frame=first+32, resume_frame=first+40))
    packets.extend([bytes(23)]*60)
    return packets, cases


def build(candidate, out):
    if out.exists():
        raise ValueError('Fresh cases required')
    game = json.loads((candidate/'manifest.json').read_text())
    image = (candidate/'native-cpu.sfc').read_bytes()
    if sha(candidate/'native-cpu.sfc') != game['rom_sha256'] or game['spc_sha256'] != ENGINE_SHA:
        raise ValueError('Unbound or different engine')
    at = game['sweep_driver_rom_offset']
    engine = image[at:at+game['sweep_driver_layout']['engine_bytes']]
    packets, cases = stimulus()
    source = out/'source'; source.mkdir(parents=True)
    (source/'engine.bin').write_bytes(engine)
    (source/'stream.bin').write_bytes(b''.join(b'\1'+p for p in packets))
    if sha(source/'engine.bin') != ENGINE_SHA:
        raise ValueError('Wrong extracted engine')
    paths = [Path(__file__), Path('tests/test_startup_pitch_cases.py'),
             candidate/'manifest.json', candidate/'native-cpu.sfc', source/'engine.bin', source/'stream.bin']
    (source/'manifest.json').write_text(json.dumps(dict(source_frames=len(packets), packets=len(packets),
        cases=cases, source_rom_sha256=game['rom_sha256'], spc_sha256=ENGINE_SHA,
        sources={str(p): sha(p) for p in paths}, scope=__doc__, release_ready=False), indent=2)+'\n')
    build_trial(source, candidate, out/'players')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
