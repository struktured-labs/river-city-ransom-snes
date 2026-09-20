"""Reverse the exact fusion patch from a qualified fused-build encounter state."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import retained_producer_replay as replay
from tools.build_sprite_fused_guarded import build
from tools.benchmark_report import sha


def guarded(parent, trial, variant, snapshot_pc):
    if variant != 'retained-producer':
        raise ValueError('Unexpected replay adapter call')
    for name in ('native_boot.lbl', 'native_runtime.lbl'):
        if (parent/name).read_bytes() != (trial/name).read_bytes():
            raise ValueError('External linked code moved')
    with tempfile.TemporaryDirectory(prefix='rcr-unfused-check-') as directory:
        fresh = Path(directory)/'candidate'
        build(trial, fresh)
        if (fresh/'native-cpu.sfc').read_bytes() != (parent/'native-cpu.sfc').read_bytes():
            raise ValueError('Only the exact freshly rebuilt fusion may be reversed')
    old = (parent/'native-cpu.sfc').read_bytes()
    new = (trial/'native-cpu.sfc').read_bytes()
    changed = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    pc = snapshot_pc & 0x3fffff
    if any(pc-3 <= i <= pc+3 for i in changed):
        raise ValueError('Checkpoint overlaps changed instruction')
    return dict(parent_rom_sha256=sha(parent/'native-cpu.sfc'),
                trial_rom_sha256=sha(trial/'native-cpu.sfc'),
                variant='reverse-sprite-fused', changed_bytes=len(changed))


def run(core, candidate, normal, checkpoint_report, frame, frames, out, trial, resume_control):
    proof = json.loads(checkpoint_report.read_text())
    selected = [s for s in proof['checkpoints'] if s['frame'] == frame]
    if len(selected) != 1 or not selected[0]['registers']['p'] & 0x100:
        raise ValueError('Need emulation-mode checkpoint outside native converter')
    original = replay.guarded_variant
    replay.guarded_variant = guarded
    try:
        passed = replay.replay(core, candidate, normal, checkpoint_report, frame, frames, out,
                               trial=trial, resume_control=resume_control)
    finally:
        replay.guarded_variant = original
    report = json.loads((out/'report.json').read_text())
    meta = json.loads((candidate/'manifest.json').read_text())
    for p, h in meta['experimental_sprite_fused_copy']['sources'].items():
        if sha(Path(p)) != h:
            raise ValueError('Changed fusion dependency')
    report['sources'].update(meta['experimental_sprite_fused_copy']['sources'])
    report['sources'][str(Path(__file__))] = sha(Path(__file__))
    report['scope'] = (__doc__+' Guard substitution is source-bound. Requires passing same-ROM '
                       'uninterrupted video/state/input/PCM control and identical initial full '
                       'WRAM/registers. No input retiming, changed trace clock or erased differences. '
                       'Trial is the older unfused cartridge, not a new release candidate.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('core', 'candidate', 'normal', 'checkpoint-report', 'out', 'trial', 'resume-control'):
        p.add_argument('--'+k, type=Path, required=True)
    for k in ('frame', 'frames'):
        p.add_argument('--'+k, type=int, required=True)
    raise SystemExit(0 if run(**vars(p.parse_args())) else 1)
