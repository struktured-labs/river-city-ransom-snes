"""Per-voice fidelity metrics vs the NES for SNES audio builds (solo-voice captures).

Root holds benchmark captures <target>-<scene>-v<N> (N: 0 mix, 1/2 pulses,
3 triangle, 4 noise), as made for docs/NESTED-AUDIO.md. Metrics:

- triangle_cutoffs: frames of the triangle stem with a second difference
  |x[n+1] - 2x[n] + x[n-1]| > 1000, i.e. a corner far sharper than the wave
  itself: a mid-wave cut to zero or a restart. (The NES 4-bit staircase stays
  below this; it shows 1 frame per scene.)
- mix_clicks: same detector on the full mix (audio_audit method).
- sweeps: pitch glides on each pulse (>=3 frames moving 0.4-12 %/frame,
  >=60 cents total) with their total cents; compared with the NES glides at
  the same scenario frame (+-3 frames).
- sweep_frame_match_pct: NES sweep frames where the build is within half a
  semitone (frame-aligned).
- noise_centroid_hz: median spectral centroid on active noise frames.
- duty_pct and pulse_hf_ratio (energy above 6 kHz / total on pulse stems:
  a measure of edge sharpness).
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import signal

from tools.compare_voice_stems import (SR, HOP, aligned, frame_table, load, f0_frames, pulse_stats,
                                       noise_stats, per_frame)

SCENES = ('menu-audio', 'combat-knockdown-audio', 'traversal-mall')


def bursts(x):
    sos = signal.butter(4, 7000, 'hp', fs=SR, output='sos')
    hf = signal.sosfilt(sos, x)
    pk = np.array([np.abs(hf[a:a + HOP]).max() for a in range(0, len(hf) - HOP, HOP)])
    med = np.array([np.median(pk[max(0, i - 30):i + 31]) for i in range(len(pk))])
    return int(np.sum(pk > np.maximum(8 * med, 1500)))


def cutoffs(x, threshold=1000):
    return len(set((np.where(np.abs(np.diff(x, 2)) > threshold)[0] // HOP).tolist()))


def glides(pf):
    by = {}
    for k in pf:
        if not k[0].startswith(('boot', 'wait')):
            by.setdefault(k[0], []).append(k[1])
    res = []
    for ph, offs in by.items():
        offs = sorted(offs)
        f = [pf[(ph, o)][0] for o in offs]
        run, d0, start = [], 0, 0
        def flush(end):
            if len(run) >= 3 and abs(sum(run)) >= 60:
                res.append((ph, offs[start], len(run), round(sum(run))))
        for i in range(1, len(f)):
            a, b = f[i - 1], f[i]
            ok = a > 0 and b > 0 and 0.004 < abs(b / a - 1) < 0.12
            d = (1 if b > a else -1) if ok else 0
            if ok and (d == d0 or not run):
                if not run:
                    start = i - 1
                run.append(1200 * np.log2(b / a)); d0 = d
            else:
                flush(i)
                run = [1200 * np.log2(b / a)] if ok else []
                start, d0 = i - 1, d
        flush(len(f))
    return sorted(res)


def match_glides(ref, cand, tol=3):
    used, pairs = set(), []
    for g in ref:
        best = None
        for j, c in enumerate(cand):
            if j in used or c[0] != g[0] or abs(c[1] - g[1]) > tol or (c[3] > 0) != (g[3] > 0):
                continue
            if best is None or abs(c[1] - g[1]) < abs(cand[best][1] - g[1]):
                best = j
        if best is not None:
            used.add(best); pairs.append((g, cand[best]))
    return pairs, [c for j, c in enumerate(cand) if j not in used]


def hf_ratio(x, cut=6000):
    f, p = signal.welch(x, SR, nperseg=4096)
    return float(p[f > cut].sum() / max(p.sum(), 1e-12))


def metrics(root, targets, scenes=SCENES):
    out = {}
    for scene in scenes:
        nes_gl = {v: glides(per_frame(root / f'nes-{scene}-v{v}')) for v in (1, 2)}
        al = {v: aligned(root, scene, [t for t in targets if t != 'nes'], v) for v in (1, 2, 4)}
        for t in targets:
            r = {}
            r['mix_clicks'] = bursts(load(root / f'{t}-{scene}-v0'))
            r['triangle_cutoffs'] = cutoffs(load(root / f'{t}-{scene}-v3'))
            nx = load(root / f'{t}-{scene}-v4')
            r['noise_centroid_hz'] = noise_stats(nx)['centroid_hz_median']
            for v in (1, 2):
                x = load(root / f'{t}-{scene}-v{v}')
                ps = pulse_stats(f0_frames(x))
                g = glides(per_frame(root / f'{t}-{scene}-v{v}'))
                pr = {'duty_pct': ps['duty_pct'], 'hf_ratio': round(hf_ratio(x), 4), 'glides': len(g)}
                if t != 'nes':
                    pairs, extra = match_glides(nes_gl[v], g)
                    err = [abs(c[3] - n[3]) for n, c in pairs]
                    pr.update(nes_glides=len(nes_gl[v]), matched=len(pairs), extra=len(extra),
                              cents_err_median=int(np.median(err)) if err else None,
                              sweep_frame_match_pct=al[v][t]['sweep_match_pct'],
                              pitch_match_pct=al[v][t]['pitch_match_pct'])
                r[f'pulse{v}'] = pr
            if t != 'nes':
                r['noise_centroid_ratio_vs_nes'] = al[4][t].get('noise_centroid_ratio_median')
            out[f'{scene}/{t}'] = r
    return out


def title_sweeps(root, targets, scene='menu-audio', v=1):
    return {t: glides(per_frame(root / f'{t}-{scene}-v{v}')) for t in targets}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--targets', nargs='+', default=['nes', '4302', '4304'])
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    m = metrics(a.root, a.targets)
    m['title_pulse1_sweeps'] = title_sweeps(a.root, a.targets)
    a.out.write_text(json.dumps(m, indent=1, default=str) + '\n')
    for k, v in m.items():
        print(k, json.dumps(v, default=str))


if __name__ == '__main__':
    main()
