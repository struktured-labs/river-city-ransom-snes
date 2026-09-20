"""Localize capture-branch correspondence changes against observed common PCM."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_raw_monitor_audio import locate
from tools.audit_capture_branch_windows import scan
from tools.benchmark_report import sha


def compare(common, raw, aac, raw_offset, rate=48000):
    aligned_aac = locate(common, aac, 4*rate, 7*rate)
    aligned_raw = locate(common, raw, 4*rate+raw_offset, 7*rate+raw_offset)
    aac_rows = scan(common, aac, aligned_aac['offset_samples'], rate,
                    4*rate, 23*rate, rate, 128)
    raw_rows = scan(common, raw, aligned_raw['offset_samples'], rate,
                    4*rate+raw_offset, 23*rate+raw_offset, rate, 128)
    return dict(common_vs_aac_alignment=aligned_aac, common_vs_raw_alignment=aligned_raw,
                common_vs_aac_windows=aac_rows, common_vs_raw_windows=raw_rows)


def audit(decoded, audio, episode, aac, out):
    if out.exists():
        raise ValueError('Need fresh output')
    d = bound_report(decoded/'report.json')
    a = bound_report(audio/'report.json')
    e = bound_report(episode/'report.json')
    for name, digest in d['artifacts'].items():
        if sha(decoded/name) != digest:
            raise ValueError('Decoded PCM changed')
    raw_path = Path(e['remote_out'])/'raw-monitor.wav'
    for p in (raw_path, aac, episode/'report.json'):
        if a['sources'].get(str(p)) != sha(p):
            raise ValueError('Different physical audio episode')
    index = d['packet_index']
    if not index[0]['common_clock']/1e9 < e['ready_received_monotonic'] < e['input_finished_monotonic'] < index[-1]['common_clock']/1e9:
        raise ValueError('Common PCM capture did not bracket input')
    ir, original = wavfile.read(decoded/'input.wav')
    cr, common = wavfile.read(decoded/'common.wav')
    rr, raw = wavfile.read(raw_path)
    ar, recording = wavfile.read(aac)
    if not ir == cr == rr == ar == 48000 or original.dtype != np.int16 or common.dtype != np.float32 or raw.dtype != np.int32 or recording.dtype != np.float32:
        raise ValueError('Unexpected native formats')
    if original.shape[1:] != (2,) or common.shape[1:] != (2,) or raw.shape[1:] != (4,) or recording.shape[1:] != (2,) or np.any(raw[:,2:]):
        raise ValueError('Unexpected channel layout')
    # This exact comparison is declared before inspecting payload equality.
    # No fitted gain: signed16 -> float is the specified numerical conversion.
    conversion = original.astype(np.float32)/32768
    equal_shape = conversion.shape == common.shape
    exact = equal_shape and np.array_equal(conversion, common)
    result = compare(common.mean(axis=1), raw[:,:2].mean(axis=1)/2147483648,
                     recording.mean(axis=1), a['alignment']['offset_samples'])
    result.update(input_common_same_shape=equal_shape, input_common_exact_s16_conversion=exact,
        input_common_differing_samples=None if not equal_shape else int(np.count_nonzero(conversion != common)),
        input_nonzero_samples=d['input_nonzero_samples'],
        common_nonzero_samples=d['common_nonzero_samples'],
        common_trace_brackets_input=True, observer_neutral_verified=False,
        fixed_lag_failure_waived=False, physical_audio_fixed=False,
        scope='Common PCM is compared separately to AAC and raw monitor, each with an early '
              'fixed alignment and all later one-second windows retained. Local lag searches are '
              'diagnostic, never applied to PCM. No gain fit, resampling, gap removal or perceptual '
              'certification. Source observation is still downstream of MiSTer/HDMI/DeckLink.',
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/audit_raw_monitor_audio.py'),
            Path('tools/audit_capture_branch_windows.py'), Path('tools/audit_capture_branch_step.py'),
            decoded/'report.json', decoded/'input.wav', decoded/'common.wav', audio/'report.json',
            episode/'report.json', raw_path, aac)})
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('decoded', 'audio', 'episode', 'aac', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
