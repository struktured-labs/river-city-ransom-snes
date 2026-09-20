"""Same-state two-port replay, admitting only an exact PPU fast-write composition."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import replay_combat_checkpoint as engine
from tools.retained_producer_replay import bind
from tools.benchmark_report import sha
from tools.build_ppu_register_trial import build, HELPER, SIZE
from tools.build_ring_tile_trial import build as build_tile
from tools.build_retained_producer_guard import symbols
from tools.two_player_combat import installed_policy, two_ports


def guarded_variant(parent,trial,variant,snapshot_pc):
    if variant not in ('ppu','ppu-tile'):
        raise ValueError('Wrong patch composition')
    for name in ('native_boot.lbl','native_runtime.lbl'):
        if (parent/name).read_bytes() != (trial/name).read_bytes():
            raise ValueError('Code moved')
    labels = symbols(parent/'native_runtime.lbl')
    low = snapshot_pc&65535
    ranges = [(labels['dispatch_write'],labels['mark_ppu_dirty']),(HELPER,HELPER+SIZE)]
    if variant=='ppu-tile':
        ranges += [(labels['bulk_ring_bytes'],labels['native_ring_consumer']),(0x6900,0x6a00)]
    if any(first<=low<last for first,last in ranges):
        raise ValueError('Checkpoint inside changed path')
    with tempfile.TemporaryDirectory(prefix='rcr-ppu-register-replay-') as directory:
        root = Path(directory)
        base = parent
        if variant=='ppu-tile':
            base = root/'tile'
            build_tile(parent,base)
        fresh = root/'trial'
        build(base,fresh)
        names = ['native-cpu.sfc','ppu-register.bin']
        if variant=='ppu-tile':
            names.append('ring-dirty.bin')
        if any((fresh/name).read_bytes() != (trial/name).read_bytes() for name in names):
            raise ValueError('Trial differs from exact rebuilt composition')
    if sha(trial/'native-cpu.sfc') != json.loads((trial/'manifest.json').read_text())['rom_sha256']:
        raise ValueError('Changed trial')
    return dict(parent_rom_sha256=sha(parent/'native-cpu.sfc'),
                trial_rom_sha256=sha(trial/'native-cpu.sfc'),variant=variant)


def replay(core,candidate,normal,checkpoint_report,frame,frames,out,trial=None,resume_control=None,variant='ppu'):
    if (trial is None) != (resume_control is None):
        raise ValueError('Trial needs same-ROM control')
    original = engine.guarded_variant
    engine.guarded_variant = guarded_variant
    records = []
    try:
        with installed_policy(),two_ports(core,records):
            passed = engine.replay(core,candidate,normal,checkpoint_report,frame,frames,out,
                trial=trial,variant=variant if trial else None,resume_control=resume_control)
    finally:
        engine.guarded_variant = original
    reference = json.loads((normal/'two-port-input.json').read_text())[frame:frame+frames]
    if len(records) != frames or any({k:v for k,v in a.items() if k!='frame'} !=
            {k:v for k,v in b.items() if k!='frame'} for a,b in zip(records,reference)):
        raise ValueError('Wrong actual two-port input stream')
    extra = [Path(__file__),Path('tools/build_ppu_register_trial.py'),Path('snes/ppu_register_fast.asm'),
             Path('snes/ppu_register_fast.cfg'),normal/'two-port-input.json']
    if trial:
        extra += [trial/'manifest.json',trial/'ppu-register.bin',trial/'ppu-register.lbl']
    if variant=='ppu-tile':
        extra += [Path('tools/build_ring_tile_trial.py'),Path('snes/ring_tile_cache.asm'),
                  Path('snes/ring_stride_cache.asm'),Path('snes/ring_stride_cache.cfg'),
                  Path('tools/build_ring_stride_trial.py')]
    bind(out,'report.json',records,extra)
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core','candidate','normal','checkpoint-report','out'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('frame','frames'):
        p.add_argument('--'+name,type=int,required=True)
    for name in ('trial','resume-control'):
        p.add_argument('--'+name,type=Path)
    p.add_argument('--variant',choices=('ppu','ppu-tile'),default='ppu')
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
