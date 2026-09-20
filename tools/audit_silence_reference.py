"""Find sustained NES activity inside same-command SNES digital-silence gaps.

Diagnostic only: different filters/clocks and frame-batched NES writes preclude
cycle-exact equivalence. No phase, gain, sample-rate or time fitting. This adds
coverage for envelopes/sweeps that the constant-held-voice gate cannot classify.
"""
import argparse
from bisect import bisect_right
import json
from pathlib import Path
import wave

import numpy as np

from tools.audit_recorded_transients import zero_runs
from tools.audit_stimulus_audio import verify_sources
from tools.benchmark_report import sha, verify_capture


def frame_energy(pcm, rows, *, nes):
    if pcm.dtype != np.dtype('<i2') or pcm.ndim != 2 or pcm.shape[1] != 2:
        raise ValueError('Need stereo PCM16')
    result = []
    previous = None
    for frame, row in enumerate(rows, 1):
        if row['source_frame' if nes else 'frame'] != frame:
            raise ValueError('Missing or reordered source frames')
        start = row['start_sample' if nes else 'audio_start_sample']
        end = row['end_sample'] if nes else start + row['audio']['samples']
        if not 0 <= start < end <= len(pcm) or (previous is not None and start != previous):
            raise ValueError('Incomplete or discontinuous audio callbacks')
        data = pcm[start:end].astype(np.float64)
        ac = np.sqrt(np.mean((data-data.mean(axis=0))**2, axis=0))
        result.append(dict(frame=frame, start=start, end=end, ac_rms=ac.tolist(),
                           peak=int(np.abs(data).max())))
        previous = end
    if not result: raise ValueError('Empty timeline')
    return result


def diagnose(pcm, rate, snes_frames, nes_frames, minimum_ms=10, ac_threshold=32):
    if (type(rate) is not int or rate <= 0 or not np.isfinite(minimum_ms)
            or minimum_ms <= 0 or not np.isfinite(ac_threshold) or ac_threshold <= 0):
        raise ValueError('Need positive rate and fixed thresholds')
    if len(snes_frames) != len(nes_frames) or not snes_frames:
        raise ValueError('Need identical complete source-frame coverage')
    starts = [r['start'] for r in snes_frames]
    gaps = []
    for begin, end in zero_runs(pcm):
        if (end-begin)*1000 < rate*minimum_ms: continue
        first, last = bisect_right(starts, begin), bisect_right(starts, end-1)
        # Discard one callback at each gap boundary, regardless of its content.
        # This is a declared boundary guard, not optimized waveform alignment.
        interior = []
        for frame in range(first+1, last):
            source, reference = snes_frames[frame-1], nes_frames[frame-1]
            if not begin <= source['start'] < source['end'] <= end:
                raise ValueError('Interior is not completely silent')
            interior.append(dict(source_frame=frame, **reference,
                reference_active=min(reference['ac_rms']) > ac_threshold))
        longest = run = 0
        for row in interior:
            run = run+1 if row['reference_active'] else 0
            longest = max(longest, run)
        gaps.append(dict(first_sample=begin,end_sample=end,
            first_frame=first,last_frame=last,milliseconds=(end-begin)*1000/rate,
            reference_frames=interior, longest_active_reference_run=longest,
            sustained_reference_activity=longest >= 3,
            classification=('reference_activity_in_snes_silence' if longest >= 3 else
                            'no_guarded_interior' if not interior else 'not_flagged')))
    return dict(gaps=gaps, sustained_mismatch_count=sum(g['sustained_reference_activity'] for g in gaps),
                boundary_guard_frames=1, minimum_consecutive_active_frames=3,
                reference_ac_threshold=ac_threshold, minimum_ms=minimum_ms)


def read_audio(path):
    with wave.open(str(path)) as f:
        if f.getnchannels()!=2 or f.getsampwidth()!=2: raise ValueError('Need stereo PCM16')
        return f.getframerate(), np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,2)


def audit(capture, replay, provenance, out):
    receipt, rows = verify_capture(capture)
    reference = verify_sources(replay/'report.json')
    proof = verify_sources(provenance/'report.json')
    if (not receipt['capture_complete'] or not proof['observer_neutral'] or
            reference['timing'] != 'publication-frame' or reference['source_frames'] != len(rows) or
            reference['sources'].get(str(capture/'capture.json')) != sha(capture/'capture.json') or
            reference['sources'].get(str(provenance/'report.json')) != sha(provenance/'report.json') or
            proof['rom_sha256'] != receipt['rom_sha256'] or proof['audio_sha256'] != receipt['audio_sha256']):
        raise ValueError('Need full neutral game capture and same-publication NES replay')
    rate, pcm = read_audio(capture/'audio.wav')
    nes_rate, nes_pcm = read_audio(replay/'audio.wav')
    nes_rows = json.loads((replay/'timeline.json').read_text())
    snes_frames = frame_energy(pcm,rows,nes=False)
    nes_frames = frame_energy(nes_pcm,nes_rows,nes=True)
    result = diagnose(pcm,rate,snes_frames,nes_frames)
    controls = []
    for phase in ('menu','idle','observe_shop','park_00_east_sweep'):
        window = next((list(range(i,i+5)) for i in range(len(rows)-4)
                       if all(rows[j]['phase']==phase and min(nes_frames[j]['ac_rms'])>32
                              for j in range(i,i+5))), None)
        if window is None: continue
        begin,end=snes_frames[window[0]]['start'],snes_frames[window[-1]]['end']
        muted=pcm.copy();muted[begin:end]=0
        negative=diagnose(muted,rate,snes_frames,nes_frames)
        caught=any(g['sustained_reference_activity'] and g['first_sample']<=begin
                   and g['end_sample']>=end for g in negative['gaps'])
        controls.append(dict(phase=phase,first_frame=window[0]+1,last_frame=window[-1]+1,
                             first_sample=begin,end_sample=end,rejected=caught))
    if not controls or not all(c['rejected'] for c in controls):
        raise ValueError('Injected same-reference silence was not detected')
    result.update(rom_sha256=receipt['rom_sha256'],source_frames=len(rows),
        native_rates=dict(snes=rate,nes=nes_rate),same_captured_write_sequence=True,
        injected_five_callback_silence=controls,
        # No hardware APU trace was captured: these are emulator commands.
        physical_events_correlated=False,synthesis_fidelity_verified=False,release_ready=False,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_recorded_transients.py'),
            Path('tools/audit_stimulus_audio.py'),Path('tools/benchmark_report.py'),
            capture/'capture.json',capture/'timeline.json',capture/'audio.wav',
            replay/'report.json',replay/'timeline.json',replay/'audio.wav',provenance/'report.json')},
        scope='Same emulator-captured ordered APU writes, scheduled at actual SPC publication frames '
              'on NES. Native-rate PCM, no time/phase/gain fit. Each complete SNES zero gap retains '
              'its NES interior callback energies, with one callback guard at each end. Three '
              'consecutive interiors above fixed AC RMS32 in both NES channels flag a diagnostic '
              'mismatch. Not flagging does not prove a rest is intentional. No physical-event '
              'correlation, NES-cycle equivalence, full-game speed or pop-free claim.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('source_frames','native_rates','sustained_mismatch_count')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','replay','provenance','out'):parser.add_argument('--'+name,type=Path,required=True)
    audit(**vars(parser.parse_args()))
