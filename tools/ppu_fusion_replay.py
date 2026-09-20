"""Exact-state combat replay admitting only rebuilt full-stub fusion variants."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import replay_combat_checkpoint as engine
from tools.retained_producer_replay import bind
from tools.benchmark_report import sha
from tools.build_ppu_fusion_trial import build, HELPER, SIZE
from tools.build_ring_tile_trial import build as build_tile
from tools.build_retained_producer_guard import symbols
from tools.two_player_combat import installed_policy, two_ports


def guarded_variant(parent, trial, variant, snapshot_pc):
    if variant not in ('fusion', 'fusion-tile'):
        raise ValueError('Wrong patch composition')
    for name in ('native_boot.lbl', 'native_runtime.lbl'):
        if (parent/name).read_bytes() != (trial/name).read_bytes():
            raise ValueError('Code moved')
    labels = symbols(parent/'native_runtime.lbl')
    low = snapshot_pc & 65535
    # Reject interrupted callers as well as helpers: a saved return address
    # alone is not proof that an in-flight private ABI can be substituted.
    ranges = [(0x6000, HELPER+SIZE),
              (labels['dispatch_write'], labels['mark_ppu_dirty'])]
    if variant == 'fusion-tile':
        ranges.append((labels['bulk_ring_bytes'], labels['native_ring_consumer']))
    if any(first <= low < last for first, last in ranges):
        raise ValueError('Checkpoint inside changed path')
    with tempfile.TemporaryDirectory(prefix='rcr-ppu-fusion-replay-') as directory:
        root = Path(directory)
        base = parent
        if variant == 'fusion-tile':
            base = root/'tile'
            build_tile(parent, base)
        fresh = root/'trial'
        build(base, fresh)
        names = ['native-cpu.sfc', 'ppu-fusion.bin']
        if variant == 'fusion-tile':
            names.append('ring-dirty.bin')
        if any((fresh/name).read_bytes() != (trial/name).read_bytes() for name in names):
            raise ValueError('Trial differs from exact rebuilt composition')
    if sha(trial/'native-cpu.sfc') != json.loads((trial/'manifest.json').read_text())['rom_sha256']:
        raise ValueError('Changed trial')
    return dict(parent_rom_sha256=sha(parent/'native-cpu.sfc'),
                trial_rom_sha256=sha(trial/'native-cpu.sfc'), variant=variant)


def replay(core, candidate, normal, checkpoint_report, frame, frames, out,
           trial=None, resume_control=None, variant='fusion'):
    if (trial is None) != (resume_control is None):
        raise ValueError('Trial needs same-ROM control')
    original = engine.guarded_variant
    engine.guarded_variant = guarded_variant
    records = []
    try:
        with installed_policy(), two_ports(core, records):
            passed = engine.replay(core, candidate, normal, checkpoint_report,
                frame, frames, out, trial=trial, variant=variant if trial else None,
                resume_control=resume_control)
    finally:
        engine.guarded_variant = original
    reference = json.loads((normal/'two-port-input.json').read_text())[frame:frame+frames]
    if len(records) != frames or any({k:v for k,v in a.items() if k != 'frame'} !=
            {k:v for k,v in b.items() if k != 'frame'} for a,b in zip(records, reference)):
        raise ValueError('Wrong actual two-port input stream')
    extra = [Path(__file__), Path('tools/build_ppu_fusion_trial.py'),
             Path('snes/ppu_stub_fusion.asm'), Path('snes/ppu_register_fast.cfg'),
             normal/'two-port-input.json']
    if trial:
        extra += [trial/'manifest.json', trial/'ppu-fusion.bin', trial/'ppu-fusion.lbl']
    if variant == 'fusion-tile':
        extra += [Path('tools/build_ring_tile_trial.py'), Path('snes/ring_tile_cache.asm'),
                  Path('snes/ring_stride_cache.asm'), Path('snes/ring_stride_cache.cfg'),
                  Path('tools/build_ring_stride_trial.py')]
    bind(out, 'report.json', records, extra)
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'candidate', 'normal', 'checkpoint-report', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    for name in ('frame', 'frames'):
        p.add_argument('--'+name, type=int, required=True)
    for name in ('trial', 'resume-control'):
        p.add_argument('--'+name, type=Path)
    p.add_argument('--variant', choices=('fusion', 'fusion-tile'), default='fusion')
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
