"""Compare per-voice audio stems (NES vs SNES builds): duty, pitch/sweep, triangle, noise, pops.

Input directories are benchmark captures (audio.wav + timeline.json), one per
target and voice: <dir>/<target>-<scene>-v<N>, N=0 full mix, 1/2 pulses,
3 triangle, 4 noise. Analysis is spectral and statistical, so it tolerates the
few-frame timing differences between emulators; it is not a sample-exact diff.

Duty from harmonic ratios of a band-limited pulse with duty d:
|H_n| ~ |sin(pi n d)|/n  ->  H2/H1: 12.5%=0.92, 25%=0.71, 50%=0; H4/H1: 12.5%=0.65, 25%=0.
"""
import argparse
import json
from pathlib import Path
import wave

import numpy as np
from scipy import signal

SR = 32040
WIN = 2048
HOP = 534  # one NTSC frame at 32040 Hz


def load(d):
    w = wave.open(str(d / 'audio.wav'))
    sr, ch = w.getframerate(), w.getnchannels()
    x = np.frombuffer(w.readframes(w.getnframes()), '<i2').reshape(-1, ch).astype(float).mean(1)
    if sr != SR:
        g = np.gcd(SR, sr)
        x = signal.resample_poly(x, SR // g, sr // g)
    return x


def f0_frames(x):
    """Per-hop (f0 Hz or 0, rms, H1..H6 magnitudes)."""
    win = np.hanning(WIN)
    out = []
    for a in range(0, len(x) - WIN, HOP):
        seg = x[a:a + WIN] - x[a:a + WIN].mean()
        rms = float(np.sqrt(np.mean(seg ** 2)))
        if rms < 30:
            out.append((0.0, rms, None)); continue
        # autocorrelation pitch, 40..2000 Hz
        ac = np.correlate(seg, seg, 'full')[WIN - 1:]
        lo, hi = SR // 2000, SR // 40
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] < 0.3 * ac[0]:
            out.append((0.0, rms, None)); continue
        # refine: prefer the shortest lag with near-max correlation (avoid octave errors)
        for div in (4, 3, 2):
            l2 = int(round(lag / div))
            if l2 >= lo and ac[l2] > 0.9 * ac[lag]:
                lag = l2; break
        f0 = SR / lag
        spec = np.abs(np.fft.rfft(seg * win, 8 * WIN))
        bins = np.fft.rfftfreq(8 * WIN, 1 / SR)
        h = []
        for n in range(1, 7):
            f = n * f0
            if f > SR / 2 - 200:
                h.append(np.nan); continue
            k = int(round(f / (bins[1])))
            h.append(float(spec[max(0, k - 6):k + 7].max()))
        out.append((f0, rms, h))
    return out


def duty_class(h):
    if h is None or not h[0] or np.isnan(h[1]) or np.isnan(h[3]):
        return None
    r2, r4 = h[1] / h[0], h[3] / h[0]
    if r2 < 0.3:
        return '50'
    if r4 > 0.35:
        return '12.5'
    return '25'


def pulse_stats(frames):
    voiced = [f for f in frames if f[0] > 0]
    classes = [duty_class(f[2]) for f in voiced]
    hist = {k: classes.count(k) for k in ('12.5', '25', '50')}
    total = max(1, sum(hist.values()))
    f0s = np.array([f[0] for f in frames])
    # glide = 4+ consecutive voiced frames with monotonic f0 change of 0.3-8% per frame
    glides, run, direction = 0, 0, 0
    for a, b in zip(f0s[:-1], f0s[1:]):
        if a > 0 and b > 0 and 0.003 < abs(b / a - 1) < 0.08:
            d = 1 if b > a else -1
            run = run + 1 if d == direction else 1
            direction = d
            if run == 4:
                glides += 1
        else:
            run, direction = 0, 0
    return dict(voiced_frames=len(voiced), duty_pct={k: round(100 * v / total, 1) for k, v in hist.items()},
                f0_median=round(float(np.median([f[0] for f in voiced])), 1) if voiced else 0,
                glides=glides)


def triangle_stats(frames):
    voiced = [f for f in frames if f[0] > 0]
    r3 = [f[2][2] / f[2][0] for f in voiced if f[2] and f[2][0] and not np.isnan(f[2][2])]
    return dict(voiced_frames=len(voiced), f0_median=round(float(np.median([f[0] for f in voiced])), 1) if voiced else 0,
                h3_over_h1=round(float(np.median(r3)), 3) if r3 else None)


def noise_stats(x):
    f, t, s = signal.stft(x, SR, nperseg=1024, noverlap=1024 - HOP)
    p = np.abs(s) ** 2
    energy = p.sum(0)
    active = energy > max(1e-9, 0.02 * np.percentile(energy, 99))
    cent = (f[:, None] * p).sum(0) / np.maximum(energy, 1e-9)
    return dict(active_frames=int(active.sum()), centroid_hz_median=round(float(np.median(cent[active])), 0) if active.any() else 0,
                centroid_hz_p10_p90=[round(float(np.percentile(cent[active], q)), 0) for q in (10, 90)] if active.any() else None)


def pops(x):
    """HF-burst clicks (audio_audit method) and large single-sample steps."""
    sos = signal.butter(4, 7000, 'hp', fs=SR, output='sos')
    hf = signal.sosfilt(sos, x)
    peaks = np.array([np.abs(hf[a:a + HOP]).max() for a in range(0, len(hf) - HOP, HOP)])
    med = np.array([np.median(peaks[max(0, i - 30):i + 31]) for i in range(len(peaks))])
    clicks = int(np.sum(peaks > np.maximum(8 * med, 1500)))
    step = np.abs(np.diff(x))
    return dict(hf_clicks=clicks, clicks_per_min=round(clicks / (len(peaks) / 60.1 / 60), 2),
                steps_over_4000=int(np.sum(step > 4000)), max_step=int(step.max()),
                rms=round(float(np.sqrt(np.mean(x ** 2))), 1))


def analyse(root, targets, scenes):
    report = {}
    for scene in scenes:
        for target in targets:
            r = {}
            base = root / f'{target}-{scene}-v'
            mix = load(Path(str(base) + '0'))
            r['mix'] = pops(mix)
            for v, name in ((1, 'pulse1'), (2, 'pulse2')):
                x = load(Path(str(base) + str(v)))
                r[name] = dict(pulse_stats(f0_frames(x)), rms=round(float(np.sqrt(np.mean(x ** 2))), 1))
            x = load(Path(str(base) + '3'))
            r['triangle'] = dict(triangle_stats(f0_frames(x)), rms=round(float(np.sqrt(np.mean(x ** 2))), 1))
            x = load(Path(str(base) + '4'))
            r['noise'] = dict(noise_stats(x), rms=round(float(np.sqrt(np.mean(x ** 2))), 1))
            report[f'{scene}/{target}'] = r
            print(scene, target, json.dumps(r))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--targets', nargs='+', default=['nes', '4302', '4303'])
    p.add_argument('--scenes', nargs='+', default=['menu-audio', 'combat-knockdown-audio', 'traversal-mall'])
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.write_text(json.dumps(analyse(a.root, a.targets, a.scenes), indent=1) + '\n')


# ---------------------------------------------------------------------------
# Frame-aligned comparison against the NES reference.

def frame_table(d):
    """[(phase, offset_in_phase, start_sample@32040, n)] and the resampled stem."""
    x = load(d)
    tl = json.loads((d / 'timeline.json').read_text())
    w = wave.open(str(d / 'audio.wav'))
    scale = SR / w.getframerate()
    rows, last, off = [], None, 0
    for r in tl:
        off = off + 1 if r['phase'] == last else 0
        last = r['phase']
        rows.append((r['phase'], off, int(r['audio_start_sample'] * scale), max(1, int(r['audio']['samples'] * scale))))
    return rows, x


def yin(seg, fmin=30, fmax=2500, threshold=0.15):
    seg = seg - seg.mean()
    if np.sqrt(np.mean(seg ** 2)) < 30:
        return 0.0
    n = len(seg) // 2
    tmax = min(n, int(SR / fmin))
    d = np.array([np.sum((seg[:n] - seg[t:t + n]) ** 2) for t in range(tmax)])
    cmnd = np.ones_like(d)
    cmnd[1:] = d[1:] * np.arange(1, tmax) / np.maximum(np.cumsum(d[1:]), 1e-9)
    tmin = int(SR / fmax)
    below = np.where(cmnd[tmin:] < threshold)[0]
    if not len(below):
        return 0.0
    t = tmin + below[0]
    while t + 1 < tmax and cmnd[t + 1] < cmnd[t]:
        t += 1
    if 1 <= t < tmax - 1:  # parabolic refinement
        a, b, c = cmnd[t - 1], cmnd[t], cmnd[t + 1]
        t = t + 0.5 * (a - c) / max(a - 2 * b + c, 1e-9)
    return SR / t


def per_frame(d, win=1024):
    rows, x = frame_table(d)
    out = {}
    for phase, off, start, n in rows:
        mid = start + n // 2
        seg = x[max(0, mid - win // 2):mid + win // 2]
        if len(seg) < win:
            continue
        rms = float(np.sqrt(np.mean((seg - seg.mean()) ** 2)))
        out[(phase, off)] = (yin(seg), rms, seg)
    return out


def centroid(seg):
    p = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
    f = np.fft.rfftfreq(len(seg), 1 / SR)
    return float((f * p).sum() / max(p.sum(), 1e-9))


def aligned(root, scene, targets, voice):
    ref = per_frame(root / f'nes-{scene}-v{voice}')
    keys = sorted(ref, key=lambda k: (k[0], k[1]))
    result = {}
    for t in targets:
        cand = per_frame(root / f'{t}-{scene}-v{voice}')
        common = [k for k in ref if k in cand and not k[0].startswith(('boot', 'wait'))]
        both = [k for k in common if ref[k][0] > 0 and cand[k][0] > 0]
        match = [k for k in both if abs(np.log2(cand[k][0] / ref[k][0])) < 0.04]   # within ~half a semitone
        octave = [k for k in both if abs(abs(np.log2(cand[k][0] / ref[k][0])) - 1) < 0.04]
        # sweep frames: NES pitch moving 0.3-8 % per frame on 3 consecutive frames
        sweep = []
        for k in both:
            p, o = k
            seq = [ref.get((p, o + i)) for i in range(-1, 2)]
            if all(s and s[0] > 0 for s in seq):
                r1, r2 = seq[1][0] / seq[0][0], seq[2][0] / seq[1][0]
                if 0.003 < abs(r1 - 1) < 0.08 and 0.003 < abs(r2 - 1) < 0.08 and (r1 > 1) == (r2 > 1):
                    sweep.append(k)
        sweep_match = [k for k in sweep if k in match]
        ra = np.array([ref[k][1] for k in common]); ca = np.array([cand[k][1] for k in common])
        on_ref = ra > 30; on_cand = ca > 30
        res = dict(frames=len(common), voiced_both=len(both),
                   pitch_match_pct=round(100 * len(match) / max(1, len(both)), 1),
                   octave_off_pct=round(100 * len(octave) / max(1, len(both)), 1),
                   sweep_frames=len(sweep), sweep_match_pct=round(100 * len(sweep_match) / max(1, len(sweep)), 1),
                   gate_agree_pct=round(100 * float(np.mean(on_ref == on_cand)), 1),
                   envelope_corr=round(float(np.corrcoef(ra, ca)[0, 1]), 3) if len(common) > 2 else None)
        if voice == 4:
            act = [k for k in common if ref[k][1] > 30 and cand[k][1] > 30]
            ratio = [centroid(cand[k][2]) / max(centroid(ref[k][2]), 1) for k in act]
            res['noise_centroid_ratio_median'] = round(float(np.median(ratio)), 2) if ratio else None
        result[t] = res
    return result


def steps(root, scene, targets, threshold=4000):
    out = {}
    for t in targets:
        out[t] = {}
        for v in range(5):
            rows, x = frame_table(root / f'{t}-{scene}-v{v}')
            idx = np.where(np.abs(np.diff(x)) > threshold)[0]
            where = {}
            for i in idx:
                for phase, off, start, n in rows:
                    if start <= i < start + n:
                        where[phase] = where.get(phase, 0) + 1; break
            out[t][f'v{v}'] = dict(count=int(len(idx)), by_phase=where)
    return out
