"""Exact-state two-port replay of the rebuilt real-event collector and tail-chain."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import replay_combat_checkpoint as engine
from tools.retained_producer_replay import bind
from tools.benchmark_report import sha
from tools.build_queued_vblank_trial import build,HELPER,SIZE
from tools.build_retained_producer_guard import symbols
from tools.two_player_combat import installed_policy,two_ports


def guarded_variant(parent,trial,variant,snapshot_pc):
    if variant!='queued-vblank':raise ValueError('Wrong composition')
    for name in ('native_boot.lbl','native_runtime.lbl'):
        if (parent/name).read_bytes()!=(trial/name).read_bytes():raise ValueError('Code moved')
    labels=symbols(parent/'native_runtime.lbl');low=snapshot_pc&65535
    ranges=((labels['bulk_ring_bytes'],labels['native_ring_consumer']),
            (labels['nmi_rti_return'],labels['apu_length_write']),(HELPER,HELPER+SIZE))
    if any(a<=low<b for a,b in ranges):raise ValueError('Checkpoint inside changed path')
    with tempfile.TemporaryDirectory(prefix='rcr-queued-vblank-replay-') as directory:
        fresh=Path(directory)/'trial';build(parent,fresh)
        for name in ('native-cpu.sfc','queued-vblank.bin'):
            if (fresh/name).read_bytes()!=(trial/name).read_bytes():raise ValueError('Different exact composition')
    if sha(trial/'native-cpu.sfc')!=json.loads((trial/'manifest.json').read_text())['rom_sha256']:
        raise ValueError('Changed trial')
    return dict(parent_rom_sha256=sha(parent/'native-cpu.sfc'),trial_rom_sha256=sha(trial/'native-cpu.sfc'),variant=variant)


def replay(core,candidate,normal,checkpoint_report,frame,frames,out,trial,resume_control):
    # Old checkpoints predate queue state. Requiring all new bytes to be zero
    # is part of the cross-ROM admission, not a state fix-up after restore.
    if any((resume_control/'initial.ram').read_bytes()[0x1b87:0x1b8d]):
        raise ValueError('New queue allocation is not zero in initial state')
    old=engine.guarded_variant;engine.guarded_variant=guarded_variant;records=[]
    try:
        with installed_policy(),two_ports(core,records):
            passed=engine.replay(core,candidate,normal,checkpoint_report,frame,frames,out,
                trial=trial,variant='queued-vblank',resume_control=resume_control)
    finally:engine.guarded_variant=old
    reference=json.loads((normal/'two-port-input.json').read_text())[frame:frame+frames]
    if len(records)!=frames or any({k:v for k,v in a.items() if k!='frame'}!=
            {k:v for k,v in b.items() if k!='frame'} for a,b in zip(records,reference)):
        raise ValueError('Actual two-port input changed')
    extra=[Path(__file__),Path('tools/build_queued_vblank_trial.py'),Path('snes/queued_vblank.asm'),
           Path('snes/queued_vblank.cfg'),normal/'two-port-input.json',trial/'manifest.json',
           trial/'queued-vblank.bin',trial/'queued-vblank.lbl']
    bind(out,'report.json',records,extra)
    return passed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('frame','frames'):p.add_argument('--'+name,type=int,required=True)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
