"""Exact hardware-entry restore with a byte-for-byte rebuilt owned-queue composition."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import retained_producer_replay as base
from tools.build_owned_queue_priority import build
from tools.build_queued_read_poll import build as poll
from tools.build_ppu_fusion_trial import build as fuse
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols


def guarded_variant(parent,trial,variant,snapshot_pc):
    if variant!='retained-producer' or snapshot_pc!=symbols(parent/'native_boot.lbl')['nmi']:
        raise ValueError('Requires exact first hardware-entry instruction')
    for name in ('native_boot.lbl','native_runtime.lbl'):
        if (parent/name).read_bytes()!=(trial/name).read_bytes():raise ValueError('Code moved')
    meta=json.loads((parent/'manifest.json').read_text())
    with tempfile.TemporaryDirectory(prefix='rcr-owned-queue-replay-') as directory:
        root=Path(directory);fresh=root/'trial'
        if not meta.get('experimental_queued_vblank',{}).get('read_poll'):
            fuse(parent,root/'fusion');poll(root/'fusion',root/'poll');build(root/'poll',fresh)
        else:build(parent,fresh)
        for name in ('native-cpu.sfc','queued-vblank.bin','retained-entry.bin','retained-guard.bin'):
            if (fresh/name).read_bytes()!=(trial/name).read_bytes():raise ValueError('Different exact composition')
    if sha(trial/'native-cpu.sfc')!=json.loads((trial/'manifest.json').read_text())['rom_sha256']:
        raise ValueError('Changed cartridge')
    return dict(parent_rom_sha256=sha(parent/'native-cpu.sfc'),trial_rom_sha256=sha(trial/'native-cpu.sfc'),
        variant='owned-queue-priority',snapshot_at_hardware_entry=True)


def replay(**args):
    parent=json.loads((args['candidate']/'manifest.json').read_text())
    if not parent.get('experimental_queued_vblank') and any((args['resume_control']/'initial.ram').read_bytes()[0x1b87:0x1b8d]):
        raise ValueError('New queue allocation is not zero')
    original=base.guarded_variant;base.guarded_variant=guarded_variant
    try:passed=base.replay(**args)
    finally:base.guarded_variant=original
    path=args['out']/'report.json';report=json.loads(path.read_text())
    files=[Path(__file__),Path('tools/build_owned_queue_priority.py'),Path('tools/build_retained_wait.py'),
        Path('tools/build_retained_entry.py'),Path('tools/build_queued_read_poll.py'),
        Path('tools/build_ppu_fusion_trial.py'),args['trial']/'owned-queue-priority.asm',
        args['trial']/'retained-entry.bin',args['trial']/'retained-guard.bin',args['trial']/'manifest.json']
    report['sources'].update({str(p):sha(p) for p in files})
    path.write_text(json.dumps(report,indent=2)+'\n')
    return passed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        p.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):p.add_argument('--'+k,type=int,required=True)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
