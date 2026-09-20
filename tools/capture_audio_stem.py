"""Explicit host-only libretro voice isolation for game/stimulus diagnostics."""
import argparse
from contextlib import contextmanager
import ctypes as C
import json
from pathlib import Path

from tools.benchmark_capture import capture, sha
from tools.smoke_libretro import Variable
from tools.replay_nes_apu_stimulus import run as replay


def options_for(system, mode):
    if system not in ('nes', 'snes') or mode not in ('noise', 'without-noise', 'triangle', 'without-triangle'):
        raise ValueError('Unknown sound stem')
    prefix, count = ('snes9x_sndchan_', 8) if system == 'snes' else ('fceumm_apu_', 5)
    voice = 3 if 'triangle' in mode else 4
    isolated_voice = not mode.startswith('without-')
    return {(prefix+str(i)).encode(): (b'enabled' if (i == voice) == isolated_voice else b'disabled')
            for i in range(1, count+1)}


@contextmanager
def isolated(system, mode):
    options = options_for(system, mode)
    original, retained, queries = C.CDLL, [], {}
    updated = False
    def loader(path):
        lib = original(path)
        setter = lib.retro_set_environment
        def register(callback):
            @type(callback)
            def hooked(cmd, data):
                nonlocal updated
                # Snes9x queries options before loading/resetting the ROM,
                # which clears its stereo switch. Reapply once in retro_run.
                if cmd == 17 and not updated:
                    C.cast(data, C.POINTER(C.c_bool))[0] = True
                    updated = True
                    return True
                if cmd == 15:
                    var = C.cast(data, C.POINTER(Variable)).contents
                    if var.key in options:
                        queries[var.key.decode()] = options[var.key].decode()
                        var.value = options[var.key]
                        return True
                return callback(cmd, data)
            retained.append(hooked)
            setter.argtypes = [type(callback)]
            setter(hooked)
        lib.retro_set_environment = register
        return lib
    C.CDLL = loader
    try:
        yield queries
        if not updated or queries != {k.decode(): v.decode() for k, v in options.items()}:
            raise ValueError('Core did not query every required voice option')
    finally:
        C.CDLL = original


def game(core, rom, out, mode, scenario):
    title, walk = Path('build/reference-title-05'), Path('build/reference-walk-02')
    refs = {'menu': (title, 600), 'settings': (walk, 600), 'story': (walk, 900), 'street': (walk, 1800)}
    with isolated('snes', mode) as queries:
        capture(core, rom, 'snes', refs, out, scenario, True, True)
    path = out/'capture.json'
    report = json.loads(path.read_text())
    report['audio_stem'] = dict(mode=mode, options_queried=queries, post_load_update_delivered=True, wrapper_sha256=sha(Path(__file__)),
                               scope='Host mixer channel isolation, not the normal game mix')
    path.write_text(json.dumps(report, indent=2)+'\n')


def stimulus(core, source, bus, provenance, frames, out, mode):
    with isolated('nes', mode) as queries:
        replay(source, bus, provenance, core, frames, out, banked=True, timing='publication-frame')
    path = out/'report.json'
    report = json.loads(path.read_text())
    report['audio_stem'] = dict(mode=mode, options_queried=queries, post_load_update_delivered=True,
                               scope='Original ordered APU writes retained; host mixer channel isolation')
    report['sources'][str(Path(__file__))] = sha(Path(__file__))
    path.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--mode', required=True, choices=('noise', 'without-noise', 'triangle', 'without-triangle'))
    parser.add_argument('--rom', type=Path)
    parser.add_argument('--scenario', default='traversal-park-single-sweep')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--bus', type=Path)
    parser.add_argument('--provenance', type=Path)
    parser.add_argument('--frames', type=int)
    args = parser.parse_args()
    if args.rom:
        if any((args.source, args.bus, args.provenance, args.frames)):
            parser.error('Choose game ROM or NES stimulus, not both')
        game(args.core, args.rom, args.out, args.mode, args.scenario)
    else:
        if not all((args.source, args.bus, args.provenance, args.frames)):
            parser.error('NES stimulus requires source, bus, provenance and frames')
        stimulus(args.core, args.source, args.bus, args.provenance, args.frames, args.out, args.mode)
