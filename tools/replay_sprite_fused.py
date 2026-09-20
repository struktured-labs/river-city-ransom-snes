"""Reuse exact-state two-port replay, permitting only freshly rebuilt fused copy."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import retained_producer_replay as replay
from tools.build_sprite_fused_guarded import build
from tools.benchmark_report import sha


def guarded(parent, trial, variant, snapshot_pc):
    if variant != 'retained-producer': raise ValueError('Unexpected replay adapter call')
    for name in ('native_boot.lbl','native_runtime.lbl'):
        if (parent/name).read_bytes() != (trial/name).read_bytes(): raise ValueError('Linked code moved')
    with tempfile.TemporaryDirectory(prefix='rcr-fused-check-') as directory:
        fresh=Path(directory)/'candidate';build(parent,fresh)
        if (fresh/'native-cpu.sfc').read_bytes() != (trial/'native-cpu.sfc').read_bytes():
            raise ValueError('Cross-ROM replay differs from freshly rebuilt permitted patch')
    old=(parent/'native-cpu.sfc').read_bytes();new=(trial/'native-cpu.sfc').read_bytes()
    changed=[i for i,(a,b) in enumerate(zip(old,new)) if a != b]
    pc=snapshot_pc&0x3fffff
    if any(pc-3<=i<=pc+3 for i in changed):raise ValueError('Checkpoint overlaps changed instruction')
    return dict(parent_rom_sha256=sha(parent/'native-cpu.sfc'),trial_rom_sha256=sha(trial/'native-cpu.sfc'),
        variant='sprite-fused-guarded',changed_bytes=len(changed))


def run(core,candidate,normal,checkpoint_report,frame,frames,out,trial=None,resume_control=None):
    proof=json.loads(checkpoint_report.read_text())
    selected=[s for s in proof['checkpoints'] if s['frame']==frame]
    # Both old/new sprite-copy and full native producer bridges are native-mode.
    # Reject checkpoints inside them, including deeper calls with unchanged PC.
    if len(selected)!=1 or not selected[0]['registers']['p']&0x100:
        raise ValueError('Need emulation-mode checkpoint outside an active native producer')
    original=replay.guarded_variant
    replay.guarded_variant=guarded
    try:
        passed=replay.replay(core,candidate,normal,checkpoint_report,frame,frames,out,
                            trial=trial,resume_control=resume_control)
    finally:replay.guarded_variant=original
    report=json.loads((out/'report.json').read_text())
    files=[Path(__file__),Path('tools/build_sprite_fused_guarded.py'),Path('tools/build_sprite_fused_copy.py'),
        Path('snes/sprite_fused_copy.asm'),Path('snes/sprite_fused_copy.cfg')]
    if trial:
        files += [trial/'sprite-fused.bin',trial/'sprite-fused-guarded.asm',trial/'sprite-fused.lbl']
        meta=json.loads((trial/'manifest.json').read_text())
        for p,h in meta['experimental_sprite_fused_copy']['sources'].items():
            if sha(Path(p))!=h:raise ValueError('Changed fused build dependency')
        report['sources'].update(meta['experimental_sprite_fused_copy']['sources'])
    report['sources'].update({str(p):sha(p) for p in files})
    report['scope']=(__doc__+' Explicit guard substitution is source-bound. Same-ROM resume must '
        'first reproduce uninterrupted pixels/state/input/PCM; trial begins with identical full WRAM '
        'and CPU registers. Different later encounters and every output difference remain retained.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return passed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out'):p.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):p.add_argument('--'+k,type=int,required=True)
    for k in ('trial','resume-control'):p.add_argument('--'+k,type=Path)
    raise SystemExit(0 if run(**vars(p.parse_args())) else 1)
