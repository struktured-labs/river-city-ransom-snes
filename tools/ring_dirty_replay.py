"""Same-state two-port replay admitting only the rebuilt ring dirty-cache patch."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import replay_combat_checkpoint as engine
from tools.retained_producer_replay import bind
from tools.benchmark_report import sha
from tools.build_ring_dirty_trial import build, HELPER, SIZE
from tools.build_retained_producer_guard import symbols
from tools.two_player_combat import installed_policy, two_ports


def guarded_variant(parent, trial, variant, snapshot_pc):
    if variant != 'ring-dirty':
        raise ValueError('Wrong patch')
    for name in ('native_boot.lbl','native_runtime.lbl'):
        if (parent/name).read_bytes() != (trial/name).read_bytes():
            raise ValueError('Code moved')
    labels = symbols(parent/'native_runtime.lbl')
    low = snapshot_pc & 65535
    if labels['bulk_ring_bytes'] <= low < labels['native_ring_consumer'] or HELPER <= low < HELPER+SIZE:
        raise ValueError('Checkpoint inside changed ring path')
    with tempfile.TemporaryDirectory(prefix='rcr-ring-dirty-replay-') as directory:
        fresh = Path(directory)/'trial'
        build(parent,fresh)
        for name in ('native-cpu.sfc','ring-dirty.bin'):
            if (fresh/name).read_bytes() != (trial/name).read_bytes():
                raise ValueError('Cartridge differs from reconstructed patch')
    if sha(trial/'native-cpu.sfc') != json.loads((trial/'manifest.json').read_text())['rom_sha256']:
        raise ValueError('Changed trial')
    return dict(parent_rom_sha256=sha(parent/'native-cpu.sfc'),
                trial_rom_sha256=sha(trial/'native-cpu.sfc'),variant=variant)


def replay(core,candidate,normal,checkpoint_report,frame,frames,out,trial=None,resume_control=None):
    if (trial is None) != (resume_control is None):
        raise ValueError('Trial needs same-ROM control')
    original = engine.guarded_variant
    engine.guarded_variant = guarded_variant
    records = []
    try:
        with installed_policy(),two_ports(core,records):
            passed = engine.replay(core,candidate,normal,checkpoint_report,frame,frames,out,
                trial=trial,variant='ring-dirty' if trial else None,resume_control=resume_control)
    finally:
        engine.guarded_variant = original
    reference = json.loads((normal/'two-port-input.json').read_text())[frame:frame+frames]
    if len(records) != frames or any({k:v for k,v in a.items() if k!='frame'} !=
            {k:v for k,v in b.items() if k!='frame'} for a,b in zip(records,reference)):
        raise ValueError('Wrong actual two-port input stream')
    extra = [Path(__file__),Path('tools/build_ring_dirty_trial.py'),Path('snes/ring_dirty_cache.asm'),
             Path('snes/ring_dirty_cache.cfg'),normal/'two-port-input.json']
    if trial:
        extra += [trial/'manifest.json',trial/'ring-dirty.bin',trial/'ring-dirty.lbl']
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
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
