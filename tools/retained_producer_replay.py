"""Exact-state two-player replay admitting only the late-retained-producer patch."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import combat_campaign as combat
from tools import capture_combat_checkpoints as checkpoints
from tools import replay_combat_checkpoint as replay_tool
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import build,HELPER,symbols
from tools.two_player_combat import installed_policy,two_ports


def bind(out,name,records,extra):
    path=out/name;report=json.loads(path.read_text())
    input_path=out/'two-port-input.json'
    input_path.write_text(json.dumps(records,separators=(',',':'))+'\n')
    files=[Path(__file__),Path('tools/two_player_combat.py'),
        Path('tools/build_retained_producer_guard.py'),Path('snes/retained_producer_guard.asm'),
        Path('snes/retained_producer_guard.cfg'),input_path,*extra]
    report['sources'].update({str(p):sha(p) for p in files})
    report['two_player']=True
    path.write_text(json.dumps(report,indent=2)+'\n')


def capture(core,candidate,normal,frames,out):
    records=[]
    with installed_policy(),two_ports(core,records):
        passed=checkpoints.capture(core,candidate,normal,frames,out,'running-jumps')
    if records!=json.loads((normal/'two-port-input.json').read_text()):
        raise ValueError('Checkpoint run changed controller callbacks')
    bind(out,'checkpoint-report.json',records,[normal/'two-port-input.json'])
    return passed


def guarded_variant(parent,trial,variant,snapshot_pc):
    if variant!='retained-producer':raise ValueError('Different patch')
    for name in ('native_boot.lbl','native_runtime.lbl'):
        if (parent/name).read_bytes()!=(trial/name).read_bytes():raise ValueError('External code moved')
    labels=symbols(parent/'native_runtime.lbl');pc=snapshot_pc&65535
    if (labels['nmi_rti_return']<=pc<labels['apu_length_write'] or HELPER<=pc<HELPER+256):
        raise ValueError('Checkpoint is inside changed return/guard path')
    with tempfile.TemporaryDirectory(prefix='rcr-retained-replay-') as directory:
        fresh=Path(directory)/'trial';build(parent,fresh)
        if ((fresh/'native-cpu.sfc').read_bytes()!=(trial/'native-cpu.sfc').read_bytes() or
                (fresh/'retained-guard.bin').read_bytes()!=(trial/'retained-guard.bin').read_bytes()):
            raise ValueError('Cross-ROM replay differs from freshly assembled permitted patch')
    meta=json.loads((trial/'manifest.json').read_text())
    if sha(trial/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed trial')
    return dict(parent_rom_sha256=sha(parent/'native-cpu.sfc'),
        trial_rom_sha256=sha(trial/'native-cpu.sfc'),variant=variant,
        changed_bytes=sum(a!=b for a,b in zip((parent/'native-cpu.sfc').read_bytes(),
                                             (trial/'native-cpu.sfc').read_bytes())))


def replay(core,candidate,normal,checkpoint_report,frame,frames,out,trial=None,resume_control=None):
    if (trial is None)!=(resume_control is None):raise ValueError('Trial requires passing same-ROM control')
    original=replay_tool.guarded_variant;replay_tool.guarded_variant=guarded_variant;records=[]
    try:
        with installed_policy(),two_ports(core,records):
            passed=replay_tool.replay(core,candidate,normal,checkpoint_report,frame,frames,out,
                trial=trial,variant='retained-producer' if trial else None,resume_control=resume_control)
    finally:
        replay_tool.guarded_variant=original
    reference=json.loads((normal/'two-port-input.json').read_text())[frame:frame+frames]
    if len(records)!=frames or any({k:v for k,v in a.items() if k!='frame'}!=
        {k:v for k,v in b.items() if k!='frame'} for a,b in zip(records,reference)):
        raise ValueError('Resumed two-port input differs from original execution')
    extra=[normal/'two-port-input.json']
    if trial:extra += [trial/'manifest.json',trial/'retained-guard.bin',trial/'retained-guard.lbl']
    bind(out,'report.json',records,extra)
    return passed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='mode',required=True)
    c=subs.add_parser('capture');r=subs.add_parser('replay')
    for sub in (c,r):
        for name in ('core','candidate','normal','out'):sub.add_argument('--'+name,type=Path,required=True)
    c.add_argument('--frames',required=True)
    r.add_argument('--checkpoint-report',type=Path,required=True)
    for name in ('frame','frames'):r.add_argument('--'+name,type=int,required=True)
    for name in ('trial','resume-control'):r.add_argument('--'+name,type=Path)
    args=vars(p.parse_args());mode=args.pop('mode')
    raise SystemExit(0 if (capture if mode=='capture' else replay)(**args) else 1)
