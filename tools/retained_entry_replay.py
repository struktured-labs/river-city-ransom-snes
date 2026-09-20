"""Exact-state replay admitting only the pre-identity retained-entry patch."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import retained_producer_replay as base
from tools.benchmark_report import sha
from tools.build_retained_entry import build,HELPER,SIZE
from tools.build_retained_producer_guard import symbols


def guarded_variant(parent,trial,variant,snapshot_pc):
    if variant!='retained-producer':raise ValueError('Wrong replay dispatcher')
    boot=symbols(parent/'native_boot.lbl');low=snapshot_pc&65535
    # Exact first-instruction NMI boundary is valid; a partial displaced prefix
    # or a helper PC is not. No registers or guest RAM are fixed up on restore.
    if HELPER<=low<HELPER+SIZE or snapshot_pc>>16 in (0,0xc0) and boot['nmi']<low<boot['nmi']+7:
        raise ValueError('Checkpoint inside changed instruction sequence')
    for name in ('native_boot.lbl','native_runtime.lbl','queued-vblank.bin','retained-guard.bin'):
        if (parent/name).read_bytes()!=(trial/name).read_bytes():raise ValueError('Unrelated code changed')
    with tempfile.TemporaryDirectory(prefix='rcr-retained-entry-replay-') as directory:
        fresh=Path(directory)/'trial';build(parent,fresh)
        for name in ('native-cpu.sfc','retained-entry.bin'):
            if (fresh/name).read_bytes()!=(trial/name).read_bytes():raise ValueError('Different rebuilt patch')
    meta=json.loads((trial/'manifest.json').read_text())
    if sha(trial/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed cartridge')
    return dict(parent_rom_sha256=sha(parent/'native-cpu.sfc'),trial_rom_sha256=sha(trial/'native-cpu.sfc'),
                variant='retained-entry',snapshot_at_hardware_entry=low==boot['nmi'])


def replay(**args):
    original=base.guarded_variant;base.guarded_variant=guarded_variant
    try:passed=base.replay(**args)
    finally:base.guarded_variant=original
    path=args['out']/'report.json';r=json.loads(path.read_text())
    files=[Path(__file__),Path('tools/build_retained_entry.py'),Path('snes/retained_entry.asm'),
        Path('snes/retained_entry.cfg'),args['trial']/'retained-entry.bin',args['trial']/'retained-entry.lbl']
    r['sources'].update({str(p):sha(p) for p in files})
    path.write_text(json.dumps(r,indent=2)+'\n')
    return passed


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        parser.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):parser.add_argument('--'+k,type=int,required=True)
    raise SystemExit(0 if replay(**vars(parser.parse_args())) else 1)
