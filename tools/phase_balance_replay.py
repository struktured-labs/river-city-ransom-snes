"""Exact-state two-port replay admitting only the phase96/post-street combination."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import replay_combat_checkpoint as engine
from tools.benchmark_report import sha
from tools.build_main_phase_trial import build as build_phase, SIZE
from tools.build_phase_camera_trial import build as build_camera, BODY
from tools.build_phase_balance_trial import build as build_balance
from tools.build_retained_producer_guard import symbols
from tools.retained_producer_replay import bind
from tools.two_player_combat import installed_policy,two_ports


def guarded_variant(parent,trial,variant,snapshot_pc):
    if variant != 'phase-balance':
        raise ValueError('Wrong patch')
    for name in ('native_boot.lbl','native_runtime.lbl'):
        if (parent/name).read_bytes() != (trial/name).read_bytes():
            raise ValueError('Existing code moved')
    labels = symbols(parent/'native_runtime.lbl')
    for name,size in (('gameplay_phase_start',SIZE),('camera_publish_safe',len(BODY))):
        if labels[name] <= snapshot_pc&65535 < labels[name]+size:
            raise ValueError('Checkpoint inside changed helper')
    with tempfile.TemporaryDirectory(prefix='rcr-phase-balance-') as directory:
        root = Path(directory)
        build_phase(parent,root/'phase')
        build_camera(root/'phase',root/'camera')
        build_balance(root/'camera',root/'balance')
        if (root/'balance/native-cpu.sfc').read_bytes() != (trial/'native-cpu.sfc').read_bytes():
            raise ValueError('Different cartridge from reconstructed patch')
    if sha(trial/'native-cpu.sfc') != json.loads((trial/'manifest.json').read_text())['rom_sha256']:
        raise ValueError('Changed trial')
    return dict(parent_rom_sha256=sha(parent/'native-cpu.sfc'),trial_rom_sha256=sha(trial/'native-cpu.sfc'),variant=variant)


def replay(core,candidate,normal,checkpoint_report,frame,frames,out,trial=None,resume_control=None):
    if (trial is None) != (resume_control is None):
        raise ValueError('Trial needs passing same-ROM control')
    original = engine.guarded_variant
    engine.guarded_variant = guarded_variant
    records = []
    try:
        with installed_policy(),two_ports(core,records):
            passed = engine.replay(core,candidate,normal,checkpoint_report,frame,frames,out,
                trial=trial,variant='phase-balance' if trial else None,resume_control=resume_control)
    finally:
        engine.guarded_variant = original
    reference = json.loads((normal/'two-port-input.json').read_text())[frame:frame+frames]
    if len(records) != frames or any({k:v for k,v in a.items() if k!='frame'} !=
        {k:v for k,v in b.items() if k!='frame'} for a,b in zip(records,reference)):
        raise ValueError('Different actual controller streams')
    extra = [Path(__file__),Path('tools/build_main_phase_trial.py'),Path('tools/build_phase_camera_trial.py'),
             Path('tools/build_phase_balance_trial.py'),normal/'two-port-input.json']
    if trial:
        extra.append(trial/'manifest.json')
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
