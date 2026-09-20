"""Capture one pulse voice without changing the game or its register writes."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path

from tools import capture_audio_stem as stems
from tools.benchmark_report import sha


def pulse_options(system, mode):
    if system not in ('nes','snes') or mode not in ('pulse1','pulse2'):
        raise ValueError('Need NES/SNES pulse1/pulse2')
    prefix,count = ('snes9x_sndchan_',8) if system=='snes' else ('fceumm_apu_',5)
    voice = int(mode[-1])
    return {(prefix+str(i)).encode():b'enabled' if i==voice else b'disabled'
            for i in range(1,count+1)}


@contextmanager
def pulse_policy():
    original = stems.options_for
    stems.options_for = pulse_options
    try:
        yield
    finally:
        stems.options_for = original


def run(core,out,mode,rom=None,source=None,bus=None,provenance=None,frames=None):
    with pulse_policy():
        if rom:
            if any((source,bus,provenance,frames)):
                raise ValueError('Choose a game or stimulus capture')
            stems.game(core,rom,out,mode,'traversal-park-single-sweep')
            path = out/'capture.json'
        else:
            if not all((source,bus,provenance,frames)):
                raise ValueError('Need complete stimulus provenance')
            stems.stimulus(core,source,bus,provenance,frames,out,mode)
            path = out/'report.json'
    report = json.loads(path.read_text())
    report['pulse_isolation'] = dict(source=str(Path(__file__)),sha256=sha(Path(__file__)),
        mode=mode,scope='Host mixer isolation only; actual APU writes and game remain unchanged')
    path.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    for name in ('rom','source','bus','provenance'):
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--frames',type=int)
    parser.add_argument('--mode',choices=('pulse1','pulse2'),required=True)
    run(**vars(parser.parse_args()))
