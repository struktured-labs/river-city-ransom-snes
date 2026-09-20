"""Reuse exact checkpoint replay with only the authenticated compact-pair patch allowed."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import replay_combat_checkpoint as replay_tool
from tools.benchmark_report import sha
from tools.build_compact_pair_reprobe import HELPER, SIZE, assemble, patch
from tools.build_hidden_index_trial import assemble as scalar_assemble


def guarded_variant(parent, trial, variant, snapshot_pc):
    if variant != 'compact-pair':
        raise ValueError('Only compact-pair composition allowed')
    old, new = (p/'native-cpu.sfc' for p in (parent, trial))
    p, t = (json.loads((root/'manifest.json').read_text()) for root in (parent, trial))
    if sha(old) != p['rom_sha256'] or sha(new) != t['rom_sha256']:
        raise ValueError('Changed checkpoint cartridge')
    for name in ('native_boot.lbl', 'native_runtime.lbl'):
        if (parent/name).read_bytes() != (trial/name).read_bytes():
            raise ValueError('Linked external code moved')
    entry, end = p['hidden_compact_index']['start'], p['hidden_compact_index']['new_end']
    with tempfile.TemporaryDirectory(prefix='rcr-pair-replay-') as directory:
        root = Path(directory)
        helper = assemble(root)
        scalar, _ = scalar_assemble(root/'scalar', entry, end-entry, True)
    if helper != (trial/'pair.bin').read_bytes() or patch(old.read_bytes(), helper, scalar, entry) != new.read_bytes():
        raise ValueError('Cross-ROM replay differs from exact assembled compact-pair patch')
    pc = snapshot_pc & 0x3FFFFF
    # Even unchanged bytes inside the old helper can represent live invocation
    # scratch/return state; never restore while either helper is executing.
    if entry <= pc < end or HELPER <= pc < HELPER+SIZE:
        raise ValueError('Checkpoint is inside changed helper invocation')
    return dict(parent_rom_sha256=sha(old), trial_rom_sha256=sha(new), variant=variant,
                changed_bytes=sum(a != b for a, b in zip(old.read_bytes(), new.read_bytes())))


def replay(core, candidate, normal, checkpoint_report, frame, frames, out,
           trial=None, resume_control=None):
    if (trial is None) != (resume_control is None):
        raise ValueError('Trial and passing resume control required together')
    original = replay_tool.guarded_variant
    replay_tool.guarded_variant = guarded_variant
    try:
        passed = replay_tool.replay(core, candidate, normal, checkpoint_report, frame, frames, out,
            trial=trial, variant='compact-pair' if trial else None, resume_control=resume_control)
    finally:
        replay_tool.guarded_variant = original
    path = out/'report.json'
    report = json.loads(path.read_text())
    files = [Path(__file__), Path('tools/build_compact_pair_reprobe.py'),
             Path('tools/build_hidden_index_trial.py'), Path('snes/compact_pair_reprobe.asm'),
             Path('snes/compact_pair_reprobe.cfg'), Path('snes/hidden_direct_rows.inc')]
    if trial:
        files += [trial/'pair.bin', trial/'manifest.json']
    report['sources'].update({str(p): sha(p) for p in files})
    report['scope'] = ('Fresh-process exact replay using the existing byte-for-byte same-ROM control. '
        'This wrapper permits ONLY the assembled compact-pair helper/trampoline/checksum patch; '
        'unchanged external labels, complete initial WRAM/registers and recorded physical inputs '
        'are required. Historical instruction observers are disabled during restoration. '
        'Every output difference retained. Not equal-output game speed, physical testing or release approval.')
    path.write_text(json.dumps(report, indent=2)+'\n')
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'candidate', 'normal', 'checkpoint-report', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    for name in ('frame', 'frames'):
        p.add_argument('--'+name, type=int, required=True)
    for name in ('trial', 'resume-control'):
        p.add_argument('--'+name, type=Path)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
