"""Attribute digital silence to captured SPC packets, conservatively.

The held-voice check requires the SAME voice continuously commanded active
from two source frames before a gap through one frame after it. This excludes
ambiguous onset/offset timing without declaring those intervals correct.
"""
from bisect import bisect_right

import numpy as np

from tools.audit_recorded_transients import zero_runs
from tools.audit_gameplay_transients import validate_timeline


def voice_state(packet):
    data = bytes.fromhex(packet)
    if len(data) != 23:
        raise ValueError('Need the complete 23-byte received packet')
    active, quiet = 0, not bool(data[21] & 16)  # DMC is not modeled here.
    for voice in range(4):
        if not data[21] & (1 << voice):
            continue
        control = data[4*voice]
        if voice == 2:
            if control & 127 == 0:
                continue
            quiet = False
            period = data[10] | (data[11] & 7) << 8
            if control & 128 and period >= 2:
                active |= 1 << voice
        else:
            if control & 16 and control & 15 == 0:
                continue
            quiet = False
            # Constant volume + length halt, not an inferred envelope value.
            if control & 48 != 48 or control & 15 == 0:
                continue
            if voice < 2:
                period = data[voice*4+2] | (data[voice*4+3] & 7) << 8
                # Disabled sweep only; enabled sweep/overflow is not modeled.
                if period < 8 or data[voice*4+1] & 128:
                    continue
            active |= 1 << voice
    return active, quiet


def packet_index(packets):
    frames = [p['frame'] for p in packets]
    if not frames or frames != sorted(frames) or min(frames) < 1:
        raise ValueError('Missing or reordered packets')
    return frames, [voice_state(p['bytes']) for p in packets]


def _context(frames, indexed_states, first, last):
    # Include the retained state at the lower boundary, not only new packets.
    lo = bisect_right(frames, first-2)-1
    hi = bisect_right(frames, last+1)
    if lo < 0 or last+1 > frames[-1]:
        return dict(classification='outside_packet_coverage', held_voice_mask=0)
    states = indexed_states[lo:hi]
    held = 15
    for mask, _ in states:
        held &= mask
    quiet = all(silent for _, silent in states)
    overlap_lo = max(0, bisect_right(frames, first-1)-1)
    overlap_hi = bisect_right(frames, last)
    return dict(classification=('held_active_voice' if held else
                'commanded_silence' if quiet else 'boundary_or_unresolved'),
        held_voice_mask=held, packet_first_index=lo, packet_last_index=hi-1,
        packet_first_frame=frames[lo], packet_last_frame=frames[hi-1],
        mute_command_in_or_before_gap=any(silent for _, silent in
            indexed_states[overlap_lo:overlap_hi]))


def packet_context(packets, first, last):
    return _context(*packet_index(packets), first, last)


def analyze(pcm, rate, rows, packets, minimum_ms=10):
    if (pcm.dtype != np.dtype('<i2') or pcm.ndim != 2 or pcm.shape[1] != 2 or
            type(rate) is not int or rate <= 0 or not np.isfinite(minimum_ms) or minimum_ms <= 0):
        raise ValueError('Need stereo signed16 PCM, sample rate and positive gap bound')
    validate_timeline(rows, len(pcm), len(rows))
    frames, states = packet_index(packets)
    if frames[-1] > len(rows):
        raise ValueError('Packets outside captured callbacks')
    starts = [r['audio_start_sample'] for r in rows]
    held_frames = []
    for frame in range(1, len(rows)+1):
        context = _context(frames, states, frame, frame)
        if context['held_voice_mask']:
            held_frames.append(dict(frame=frame, voice_mask=context['held_voice_mask']))
    gaps = []
    for begin, end in zero_runs(pcm):
        if (end-begin)*1000 < rate*minimum_ms:
            continue
        first = bisect_right(starts, begin)
        last = bisect_right(starts, end-1)
        context = _context(frames, states, first, last)
        gaps.append(dict(first_sample=begin, end_sample=end, first_frame=first,
            last_frame=last, milliseconds=(end-begin)*1000/rate,
            phases=sorted({r['phase'] for r in rows[first-1:last]}), **context))
    totals = {kind: sum(g['classification'] == kind for g in gaps) for kind in
        ('held_active_voice', 'commanded_silence', 'boundary_or_unresolved', 'outside_packet_coverage')}
    return dict(gaps=gaps, classifications=totals, minimum_ms=minimum_ms,
        held_voice_frames=held_frames,
        held_voice_silence_passed=bool(held_frames) and totals['held_active_voice'] == 0,
        scope='Exact-zero gaps, not near-silence, pops, spectral fidelity or speed. '
              'The same enabled constant-volume/halted voice must stay commanded active '
              'from two frames before the gap through one after. Envelope/sweep cases '
              'are unresolved. Source-packet enable already includes checked length gating. '
              'A nearby mute command is context, not sample-exact causal attribution. '
              'No waveform alignment or gain fit. Unresolved and uncovered gaps retained.')
