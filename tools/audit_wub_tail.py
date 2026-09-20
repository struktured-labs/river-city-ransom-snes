"""Check three fixed-pitch slow pulses in actual PCM, plus unchanged game handoff."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_ident_audio import frequency
from tools.benchmark_report import sha
from tools.build_wub_tail_trial import curve, patch
from tools.build_ident_spc import curve as old_curve
from tools.check_branding_splash import evaluate


def characterize(pcm, rate, rows):
    offsets = np.cumsum([0]+[r['audio_sample_count'] for r in rows])
    if offsets[-1] != len(pcm) or pcm.dtype != np.int16 or pcm.shape[1:] != (2,):
        raise ValueError('Incomplete native stereo callback PCM')
    hold = [r for r in rows if r['phase'] == 2]
    if [r['ident_note'] for r in hold] != list(range(240)):
        raise ValueError('Missing ident command sequence')
    levels = [float(np.sqrt(np.mean(pcm[offsets[r['frame']-1]:offsets[r['frame']]].astype(float)**2))) for r in hold]
    # One16.7ms callback contains fewer than two110Hz cycles: its RMS maximum
    # can track oscillator phase instead of the2Hz loudness envelope. Use a
    # fixed centered50ms energy window (about5.5 cycles), never move audio.
    envelope = np.sqrt(np.convolve(np.square(levels), np.ones(3)/3, mode='same'))
    pulses = []
    for n in (144, 174, 204):
        peak = max(range(n, n+10), key=lambda i: envelope[i])
        trough = min(range(n+13, n+22), key=lambda i: envelope[i])
        f = hold[peak]['frame']
        block = pcm[offsets[f-2]:offsets[f+3], 0]
        hz = frequency(block, rate, 110)
        pulses.append(dict(peak_note=peak, trough_note=trough, peak_rms=float(envelope[peak]),
                           trough_rms=float(envelope[trough]), trough_ratio=float(envelope[trough]/envelope[peak]), measured_hz=hz))
    gates = dict(three_deep_pulses=all(p['peak_rms'] > 500 and p['trough_ratio'] < .35 for p in pulses),
        slow_half_second_spacing=all(28 <= b['peak_note']-a['peak_note'] <= 32 for a,b in zip(pulses,pulses[1:])),
        fixed_low_note=all(abs(p['measured_hz']/110-1) < .05 for p in pulses),
        decayed_before_stop=levels[-1] < max(levels)*.02)
    return dict(passed=all(gates.values()), gates=gates, pulses=pulses, rms_each_frame=levels,
                measurement_energy_window_frames=3)


def audit(parent, candidate, baseline, core, out):
    if out.exists():
        raise ValueError('Fresh output required')
    capture = candidate/'capture'
    meta = json.loads((candidate/'manifest.json').read_text())
    old_meta = json.loads((parent/'manifest.json').read_text())
    a = json.loads((capture/'capture.json').read_text())
    b = json.loads((baseline/'capture.json').read_text())
    for receipt, directory, manifest in ((a,candidate,meta),(b,parent,old_meta)):
        if (receipt['rom_sha256'] != sha(directory/'native-cpu.sfc') or
                receipt['rom_sha256'] != manifest['rom_sha256'] or receipt['core_sha256'] != sha(core) or
                receipt['harness_sha256'] != sha(Path('tools/capture_branding_splash.py'))):
            raise ValueError('Unbound executed ROM/core/harness')
    changed, offset = patch((parent/'native-cpu.sfc').read_bytes(), old_curve(), curve())
    if changed != (candidate/'native-cpu.sfc').read_bytes():
        raise ValueError('Trial changes more than intended tail/checksum')
    ar,x = wavfile.read(capture/'audio.wav'); br,y = wavfile.read(baseline/'audio.wav')
    if ar != br or x.shape != y.shape or len(a['frames']) != len(b['frames']):
        raise ValueError('Capture lengths/rates differ')
    positive, negative = characterize(x, ar, a['frames']), characterize(y, br, b['frames'])
    rows = a['frames']; offsets = np.cumsum([0]+[r['audio_sample_count'] for r in rows])
    handoff = next(r['frame'] for r in rows if r['phase'] == 3)
    end = next(r['frame'] for r in rows if r['phase'] == 2 and r['ident_note'] == 144)
    fields = ('phase','edge','ident_note','nmi','fault','spc_timeout','video_sha256',
              'game_ram_sha256','nonstack_game_ram_sha256','vram_zero','audio_sample_count')
    visual = evaluate(candidate)
    gates = dict(splash_checks=all(visual['gates'].values()), wub_pcm=positive['passed'],
        old_shallow_tail_rejected=not negative['gates']['three_deep_pulses'],
        all950_video_ram_timing_rows_equal=len(rows)==950 and all(all(u[k]==v[k] for k in fields) for u,v in zip(rows,b['frames'])),
        unchanged_descent_pcm=np.array_equal(x[:offsets[end-1]],y[:offsets[end-1]]),
        handoff_and_game_pcm_exact=np.array_equal(x[offsets[handoff-1]:],y[offsets[handoff-1]:]))
    result = dict(passed=all(gates.values()), gates=gates, positive=positive, negative=negative,
        splash=visual, handoff_frame=handoff, table_offset=offset, rate=ar,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/build_wub_tail_trial.py'),
            Path('tools/build_ident_spc.py'),Path('tools/check_branding_splash.py'),Path('tools/audit_ident_audio.py'),
            Path('tools/capture_branding_splash.py'),core,parent/'native-cpu.sfc',parent/'manifest.json',
            candidate/'native-cpu.sfc',candidate/'manifest.json',capture/'capture.json',capture/'audio.wav',
            baseline/'capture.json',baseline/'audio.wav')},
        subjective_timbre_approved=False, physical_audio_verified=False, release_ready=False, scope=__doc__)
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],gates=gates,pulses=positive['pulses'])))
    return result['passed']


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','baseline','core','out'):
        p.add_argument('--'+name,type=Path,required=True)
    raise SystemExit(0 if audit(**vars(p.parse_args())) else 1)
