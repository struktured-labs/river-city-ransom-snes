"""Decode the replay cartridge's complementary frame marker, without RAM edits."""
import argparse
import ctypes as C
import json
from pathlib import Path

import numpy as np

from tools import smoke_libretro as smoke
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def decode_marker(rgb, box=(64, 39, 128, 16)):
    """Fixed box, 16 LSB-first bits above their complements; reject ambiguity."""
    x, y, width, height = box
    if (rgb.ndim != 3 or rgb.shape[2] != 3 or min(x, y) < 0 or
            width < 32 or height < 4 or x+width > rgb.shape[1] or y+height > rgb.shape[0]):
        raise ValueError('Invalid marker bounds')
    bits = []
    for row in range(2):
        values = []
        for bit in range(16):
            # Inner half of each tile avoids edge ringing and scaler blends.
            left = x + int((bit+.25)*width/16)
            right = x + int((bit+.75)*width/16)
            top = y + int((row+.25)*height/2)
            bottom = y + int((row+.75)*height/2)
            tile = rgb[top:bottom, left:right]
            if tile.size and np.max(tile) < 64:
                values.append(0)
            elif tile.size and np.min(tile) > 192:
                values.append(1)
            else:
                raise ValueError('Ambiguous marker tile')
        bits.append(values)
    if any(a == b for a, b in zip(*bits)):
        raise ValueError('Marker complement mismatch')
    return sum(b << i for i, b in enumerate(bits[0]))


def rgb_frame(data, width, height, pitch, fmt):
    if fmt not in (0, 1, 2):
        raise ValueError('Unexpected pixel format')
    size = 4 if fmt == 1 else 2
    raw = np.frombuffer(C.string_at(data, pitch*height), dtype=np.uint8).reshape(height, pitch)
    v = np.ascontiguousarray(raw[:, :width*size]).view('<u4' if size == 4 else '<u2').reshape(height, width)
    if fmt == 1:
        channels = [(v >> n) & 255 for n in (16, 8, 0)]
    else:
        channels = [((v >> (11 if fmt == 2 else 10)) & 31)*255//31,
                    ((v >> 5) & (63 if fmt == 2 else 31))*255//(63 if fmt == 2 else 31),
                    (v & 31)*255//31]
    return np.stack(channels, axis=-1).astype(np.uint8)


def audit(core, fixture, reference, out):
    manifest = bound_report(fixture/'manifest.json')
    ref = bound_report(reference/'report.json')
    if not ref['passed'] or ref['receipt']['rom_sha256'] != manifest['rom_sha256']:
        raise ValueError('Wrong/incomplete replay reference')
    out.mkdir(parents=True, exist_ok=False)
    original = C.CDLL
    callbacks = []; rows = []; errors = []; fmt = 0; frame = 0
    def loader(path):
        lib = original(path)
        setter = lib.retro_set_environment
        def environment(callback):
            @type(callback)
            def hooked(cmd, data):
                nonlocal fmt
                if cmd == 10: fmt = C.cast(data, C.POINTER(C.c_int))[0]
                return callback(cmd, data)
            callbacks.append(hooked); setter.argtypes = [type(callback)]; setter(hooked)
        lib.retro_set_environment = environment
        video_setter = lib.retro_set_video_refresh
        def register(callback):
            @type(callback)
            def video(data, width, height, pitch):
                nonlocal frame
                frame += 1
                if data:
                    try:
                        value = decode_marker(rgb_frame(data, width, height, pitch, fmt))
                        rows.append(dict(host_frame=frame, source_frame=value))
                    except ValueError as error:
                        errors.append(dict(host_frame=frame, error=str(error)))
                callback(data, width, height, pitch)
            callbacks.append(video); video_setter.argtypes = [type(callback)]; video_setter(video)
        lib.retro_set_video_refresh = register
        return lib
    smoke.C.CDLL = loader
    try:
        smoke.run(core, fixture/'player.sfc', manifest['source_frames']+360,
                  out/'audio.wav', kind='adapter', screenshot=out/'last.png', ram_path=out/'memory.ram')
    finally:
        smoke.C.CDLL = original
    # The frame marker is drawn first in VBlank, before the SPC handshake.
    # Check it against the same retro_run's RAM receipt, not a fitted offset.
    reference_rows = json.loads((reference/'timeline.json').read_text())
    by_host = {r['host_frame']:r['source_frame'] for r in rows}
    mismatches = [r for r in reference_rows if by_host.get(r['host_frame']) != r['source_frame']]
    passed = not mismatches and all(sha(out/p) == sha(reference/p) for p in ('audio.wav', 'memory.ram', 'last.png'))
    result = dict(passed=passed, decoded_frames=len(rows), checked_source_frames=len(reference_rows),
        mismatches=mismatches, undecodable=errors, scope=__doc__, rows=rows,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/smoke_libretro.py'),core,
            fixture/'manifest.json',reference/'report.json',out/'audio.wav',out/'memory.ram',out/'last.png')})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=passed, decoded_frames=len(rows), mismatches=len(mismatches))))
    if not passed: raise ValueError('Visual replay marker/neutrality check failed')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core','fixture','reference','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
