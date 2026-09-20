"""Retain fixed-lag failures and diagnose changing raw/AAC lag in every window.

Diagnostic searches do not alter audio, replace the original offset, identify
the faulty branch, or certify game timing. Quiet/unsearchable windows remain.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_capture_branch_step import window
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def scan(raw, aac, offset, rate, first, last, step, radius):
    if not 0 <= first < last or step <= 0 or rate <= 0:
        raise ValueError('Invalid window range')
    rows = []
    for start in range(first, last, step):
        end = min(start+step, last)
        try:
            row = dict(searchable=True, **window(raw, aac, offset, start, end, radius))
        except ValueError as exc:
            row = dict(searchable=False, first=start, last=end, reason=str(exc))
        rows.append(row)
    return rows


def audit(audio, aac, out):
    if out.exists():
        raise ValueError('Need fresh report')
    proof = bound_report(audio/'report.json')
    if proof['sources'].get(str(aac)) != sha(aac):
        raise ValueError('AAC is not the original bound decode')
    raw_path = next(Path(p) for p in proof['sources'] if p.endswith('/raw-monitor.wav'))
    rr, raw = wavfile.read(raw_path); ar, decoded = wavfile.read(aac)
    if (rr != 48000 or ar != rr or raw.dtype != np.int32 or decoded.dtype != np.float32
            or raw.shape[1] != 4 or decoded.shape[1] != 2 or np.any(raw[:, 2:])):
        raise ValueError('Unexpected native capture format')
    x = raw[:, :2].mean(axis=1)/2147483648; y = decoded.mean(axis=1)
    offset = proof['alignment']['offset_samples']; radius = 2048
    coarse = scan(x, y, offset, rr, 4*rr, 23*rr, rr, radius)
    fine = scan(x, y, offset, rr, 4*rr, 23*rr, rr//20, radius)
    first, last = 8*rr, 9*rr
    identity = window(y, y, 0, first, last, radius)
    inserted = window(np.r_[np.zeros(776), y], y, 0, first, last, radius)
    silent = scan(np.zeros_like(y), y, 0, rr, 2*rr, 3*rr, rr, radius)
    controls = dict(identity_zero=identity['diagnostic_offset_delta'] == 0 and identity['diagnostic_correlation'] > .999999,
                    inserted776_detected=inserted['diagnostic_offset_delta'] == 776 and inserted['diagnostic_correlation'] > .999999,
                    silent_retained_unsearchable=len(silent) == 1 and not silent[0]['searchable'])
    if not all(controls.values()):
        raise ValueError('Alignment controls failed')
    report = dict(original_fixed_offset=offset, radius_samples=radius, rate=rr,
                  coarse=coarse, fine=fine, controls=controls, scope=__doc__,
                  fixed_lag_failure_waived=False, audio_changed=False, physical_audio_fixed=False,
                  original_injected_dropout_detected=proof['synthetic_100ms_aac_only_cut']['detected'],
                  sources={str(p): sha(p) for p in (Path(__file__), Path('tools/audit_capture_branch_step.py'),
                      Path('tools/audit_raw_monitor_audio.py'), audio/'report.json', aac, raw_path)})
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(coarse=coarse, controls=controls)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('audio', 'aac', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    audit(**vars(parser.parse_args()))
