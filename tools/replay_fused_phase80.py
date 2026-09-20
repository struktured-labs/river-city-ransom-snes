"""Exact-state two-port replay admitting only the bound phase96-to-phase80 change."""
import argparse
import json
from pathlib import Path
import tempfile

from tools import retained_producer_replay as replay
from tools.benchmark_report import sha
from tools.build_fused_phase80 import build
from tools.build_main_phase_trial import SIZE
from tools.build_retained_producer_guard import symbols


def guarded(parent, trial, variant, snapshot_pc):
    if variant != 'retained-producer':
        raise ValueError('Unexpected replay adapter')
    for name in ('native_boot.lbl', 'native_runtime.lbl'):
        if (parent/name).read_bytes() != (trial/name).read_bytes():
            raise ValueError('Linked code moved')
    start = symbols(parent/'native_runtime.lbl')['gameplay_phase_start']
    if start <= (snapshot_pc & 65535) < start + SIZE:
        raise ValueError('Checkpoint inside changed phase helper')
    meta = json.loads((trial/'manifest.json').read_text())
    for path, digest in meta['experimental_fused_phase80']['sources'].items():
        if sha(Path(path)) != digest:
            raise ValueError('Changed phase80 dependency')
    if sha(trial/'native-cpu.sfc') != meta['rom_sha256']:
        raise ValueError('Changed trial ROM')
    with tempfile.TemporaryDirectory(prefix='rcr-phase80-check-') as directory:
        fresh = Path(directory)/'candidate'
        build(parent, fresh)
        if (fresh/'native-cpu.sfc').read_bytes() != (trial/'native-cpu.sfc').read_bytes():
            raise ValueError('Trial differs from permitted rebuilt patch')
    old = (parent/'native-cpu.sfc').read_bytes()
    new = (trial/'native-cpu.sfc').read_bytes()
    return dict(parent_rom_sha256=sha(parent/'native-cpu.sfc'),
                trial_rom_sha256=sha(trial/'native-cpu.sfc'), variant='fused-phase80',
                changed_bytes=sum(a != b for a, b in zip(old, new)))


def run(core, candidate, normal, checkpoint_report, frame, frames, out,
        trial=None, resume_control=None):
    proof = json.loads(checkpoint_report.read_text())
    selected = [s for s in proof['checkpoints'] if s['frame'] == frame]
    if len(selected) != 1 or not selected[0]['registers']['p'] & 0x100:
        raise ValueError('Need emulation-mode checkpoint outside native producer')
    original = replay.guarded_variant
    replay.guarded_variant = guarded
    try:
        passed = replay.replay(core, candidate, normal, checkpoint_report, frame,
                               frames, out, trial=trial, resume_control=resume_control)
    finally:
        replay.guarded_variant = original
    report = json.loads((out/'report.json').read_text())
    paths = [Path(__file__), Path('tools/build_fused_phase80.py')]
    if trial:
        meta = json.loads((trial/'manifest.json').read_text())
        report['sources'].update(meta['experimental_fused_phase80']['sources'])
    report['sources'].update({str(p): sha(p) for p in paths})
    report['scope'] = (__doc__ + ' Same-ROM control must reproduce uninterrupted '
        'video, state, inputs and PCM. Trial starts at identical full WRAM/registers. '
        'Every later difference retained; no restored-state instruction clocks used.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('core', 'candidate', 'normal', 'checkpoint-report', 'out'):
        parser.add_argument('--'+key, type=Path, required=True)
    for key in ('frame', 'frames'):
        parser.add_argument('--'+key, type=int, required=True)
    for key in ('trial', 'resume-control'):
        parser.add_argument('--'+key, type=Path)
    raise SystemExit(0 if run(**vars(parser.parse_args())) else 1)
