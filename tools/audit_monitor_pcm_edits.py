"""Exact native PCM edit diagnosis; preserve ambiguity and never rewrite evidence."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def walk(reference, observed, first, last, offset, radius=128, lookahead=2048):
    if (reference.ndim != 2 or observed.ndim != 2 or reference.shape[1] != 2 or
        observed.shape[1] != 2 or not 0 <= first < last <= len(observed) or
        not 0 <= first+offset < last+offset <= len(reference) or radius < 1 or lookahead < 1):
        raise ValueError('Invalid exact PCM comparison')
    at, delta, matched, edits = first, 0, 0, []
    while at < last:
        pos = at+offset+delta
        count = min(last-at, len(reference)-pos)
        if count <= 0:
            return dict(complete=False, reason='Reference exhausted', at=at, edits=edits)
        equal = np.all(reference[pos:pos+count] == observed[at:at+count], axis=1)
        differences = np.flatnonzero(~equal)
        run = count if not len(differences) else int(differences[0])
        at += run; matched += run; pos += run
        if at == last:
            break
        if at+lookahead+radius > last or pos+lookahead+radius > len(reference):
            return dict(complete=False, reason='Insufficient tail context', at=at, edits=edits)
        candidates = []
        for skip in range(1, radius+1):
            if np.array_equal(reference[pos+skip:pos+skip+lookahead], observed[at:at+lookahead]):
                candidates.append(dict(branch='reference_only', frames=skip))
            if np.array_equal(reference[pos:pos+lookahead], observed[at+skip:at+skip+lookahead]):
                candidates.append(dict(branch='observed_only', frames=skip))
        row = dict(observed_frame=at, reference_frame=pos, candidates=candidates,
                   exact_lookahead_frames=lookahead)
        edits.append(row)
        if len(candidates) != 1:
            return dict(complete=False, reason='No unique bounded edit', at=at, edits=edits)
        candidate = candidates[0]
        if candidate['branch'] == 'reference_only':
            delta += candidate['frames']
        else:
            at += candidate['frames']; delta -= candidate['frames']
    return dict(complete=True, first=first, last=last, exact_matched_frames=matched,
                net_reference_advance=delta, edits=edits,
                deletion_boundary_unique_in_repeated_samples=False)


def audit(decoded, branch, audio, settings, out):
    if out.exists():
        raise ValueError('Need fresh report')
    d = bound_report(decoded/'report.json')
    b = bound_report(branch/'report.json')
    a = bound_report(audio/'report.json')
    config = json.loads(settings.read_text())
    gain = np.float32(config['blackmagic']['volume'])
    common_path = decoded/'common.wav'
    raw_path = next(Path(p) for p in b['sources'] if p.endswith('/raw-monitor.wav'))
    if b['sources'].get(str(common_path)) != sha(common_path) or b['sources'].get(str(audio/'report.json')) != sha(audio/'report.json'):
        raise ValueError('Different common/audio episode')
    if not b['input_common_exact_s16_conversion']:
        raise ValueError('Input/common conversion is not exact')
    rate, common = wavfile.read(common_path); rr, raw = wavfile.read(raw_path)
    if rate != 48000 or rr != rate or raw.dtype != np.int32 or common.dtype != np.float32:
        raise ValueError('Unexpected native format')
    # Declared measured gain, float32 product and truncating S32 conversion.
    # No amplitude optimization or fitted coefficient.
    scaled = common*gain*np.float32(2147483648)
    if not np.isfinite(scaled).all() or np.max(np.abs(scaled)) >= 2147483648:
        raise ValueError('Would overflow native S32')
    expected = np.trunc(scaled).astype(np.int32)
    first, last = 4*rate+a['alignment']['offset_samples'], 22*rate+a['alignment']['offset_samples']
    result = walk(expected, raw[:,:2], first, last, b['common_vs_raw_alignment']['offset_samples'])
    result.update(gain=float(gain), gain_source=str(settings), radius=128, lookahead=2048,
        pcm_changed=False, physical_audio_fixed=False, observer_neutral_verified=False,
        scope='Diagnostic bounded exact sequence matching after the measured OBS volume '
              'and declared float32-to-S32 truncation. Candidate edits are not applied to '
              'listening evidence. Nonunique candidates and unmatched tails fail. Reference-only '
              'samples indicate missing monitor correspondence under this model, not the exact '
              'physical discard instruction or an unambiguous boundary within repeated samples.',
        sources={str(p): sha(p) for p in (Path(__file__), decoded/'report.json', branch/'report.json',
            audio/'report.json', settings, common_path, raw_path)})
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('decoded', 'branch', 'audio', 'settings', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
