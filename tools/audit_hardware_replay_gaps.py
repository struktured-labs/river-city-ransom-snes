"""Compare same-command replay silence with physical audio using one held-out alignment.

RMS features are analysis only; native audio excerpts are never retimed,
normalized or resampled. Cold replay and unknown sub-frame hardware timing
prevent sample-exact causal attribution.
"""
import argparse
from bisect import bisect_right
import json
from pathlib import Path
from html import escape

import numpy as np
from scipy.io import wavfile

from tools.analyze_game_silence import voice_state
from tools.audit_dsp_latency import dac_tick
from tools.audit_main_display_latency import bound_report
from tools.audit_pulse_onset import load
from tools.audit_raw_monitor_audio import locate, score
from tools.audit_recorded_transients import zero_runs
from tools.benchmark_report import sha

STEP = .002
TRAIN = (4, 7)
HELD = (1, 2, 3, 8, 10, 12, 15, 18, 19)


def envelope(pcm, rate, full_scale):
    if pcm.ndim != 2 or pcm.shape[1] < 2 or rate <= 0 or full_scale <= 0:
        raise ValueError('Need stereo PCM and positive scales')
    mono = pcm[:, :2].astype(float).mean(axis=1) / full_scale
    if not np.isfinite(mono).all():
        raise ValueError('Nonfinite PCM')
    # Round to the nearest native sample: truncating floating-point times can
    # turn an exact 96-sample bin into 95/97 samples even at 48kHz.
    edges = np.rint(np.arange(0, len(pcm) / rate, STEP) * rate).astype(int)
    if len(edges) < 2 or np.any(np.diff(edges) <= 0):
        raise ValueError('Insufficient PCM resolution')
    squares = np.r_[0, np.cumsum(mono ** 2)]
    return np.log10(np.maximum(np.sqrt(np.maximum(0, np.diff(squares[edges])) / np.diff(edges)), 1e-7))


def overlap(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def waveform_svg(panels, limit=1):
    """Native sample polylines, fixed full-scale axes; no display gain fitting."""
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="520" '
             'viewBox="0 0 1000 520"><rect width="1000" height="520" fill="#101821"/>',
             '<g fill="#eee" font-family="sans-serif" font-size="15">']
    for index, (label, pcm, rate, scale, center) in enumerate(panels):
        top = 35 + index * 250
        start = max(0, int((center - .1) * rate))
        end = min(len(pcm), int((center + .1) * rate))
        points = ' '.join(f'{80 + ((sample / rate - center) + .1) * 4400:.2f},'
                          f'{top + 90 - float(pcm[sample, 0]) / scale * 75 / limit:.2f}'
                          for sample in range(start, end))
        parts.append(f'<text x="80" y="{top}">{escape(label)}</text>')
        for amplitude in (-limit, 0, limit):
            y = top + 90 - amplitude * 75 / limit
            parts.append(f'<path d="M80 {y} H960" stroke="#456"/>'
                         f'<text x="5" y="{y + 5}">{amplitude:+g}</text>')
        for ms in (-100, -50, 0, 50, 100):
            x = 520 + ms * 4.4
            parts.append(f'<text x="{x}" y="{top + 190}" text-anchor="middle">{ms}</text>')
        parts.append(f'<defs><clipPath id="panel{index}"><rect x="80" y="{top + 15}" width="880" height="150"/></clipPath></defs>'
                     f'<polyline points="{points}" fill="none" stroke="#7edddd" stroke-width=".7" clip-path="url(#panel{index})"/>'
                     f'<text x="80" y="{top + 215}">Full-scale amplitude; milliseconds from fixed-offset center</text>')
    return ''.join(parts) + '</g></svg>'


def register_context(writes, sample):
    registers, recent = [0] * 128, {}
    for write in writes:
        if write['tick'] > dac_tick(sample):
            break
        registers[write['register']] = write['value']
        recent[write['register']] = write
    selected = (0, 1, 0x10, 0x11, 0x20, 0x21, 0x22, 0x23, 0x25, 0x27,
                0x30, 0x31, 0x0c, 0x1c, 0x2c, 0x3c, 0x4c, 0x5c, 0x6c)
    return dict(registers={f'{r:02x}': registers[r] for r in selected},
        triangle_gain_write=recent.get(0x27),
        scope='Actual replay DSP register writes at this DAC sample. GAIN release can reach '
              'zero envelope while voice volume remains nonzero; these are not internal envelope snapshots.')


def audit(fixture, normal, observed, hardware, out):
    if out.exists():
        raise ValueError('Need fresh analysis path')
    hw = bound_report(hardware / 'report.json')
    source = bound_report(fixture / 'manifest.json')
    if source['source_rom_sha256'] != hw['diagnostic_rom_sha256']:
        raise ValueError('Different physical command source')
    onset, _, writes, ready = load(observed, normal, fixture)
    packet_records = hw['log']['records']
    if (fixture / 'stream.bin').read_bytes() != b''.join(b'\x01' + bytes.fromhex(r['packet']) for r in packet_records):
        raise ValueError('Replay does not contain exact hardware packets')
    audio_path = hardware / 'audio.json'
    audio = bound_report(audio_path)
    raw_path = next(Path(p) for p in audio['sources'] if p.endswith('/raw-monitor.wav'))
    rr, raw = wavfile.read(raw_path)
    sr, simulated = wavfile.read(normal / 'audio.wav')
    if raw.dtype != np.int32 or simulated.dtype != np.int16 or rr != 48000 or sr != 32040:
        raise ValueError('Unexpected native audio format')
    branch_offset = audio['alignment']['offset_samples']
    if branch_offset < 0:
        raise ValueError('Unsupported negative capture-branch offset')
    actual = envelope(raw[branch_offset:], rr, 2147483648)
    predicted = envelope(simulated, sr, 32768)
    first, last = [round(t / STEP) for t in TRAIN]
    aligned = locate(actual, predicted, first, last)
    shift = aligned['offset_samples']
    seconds = shift * STEP
    held = [dict(replay_first=t, fixed_offset_correlation=score(actual, predicted, shift,
        round(t / STEP), round((t + 1) / STEP))) for t in HELD]
    # Local optima quantify sensitivity only. They NEVER move evidence or
    # replace the single offset used for every gap and held-out correlation.
    sensitivity = []
    for t in HELD:
        candidates = [(score(actual, predicted, d, round(t / STEP), round((t + 1) / STEP)), d)
                      for d in range(shift - 20, shift + 21)]
        best, at = max(candidates)
        sensitivity.append(dict(replay_first=t, local_best_seconds=at * STEP, correlation=best))
    replay_gaps = [(a, b) for a, b in zero_runs(simulated) if (b - a) * 1000 >= sr * 5]
    ready_ticks = [ready[i]['tick'] for i in range(1, len(ready) + 1)]
    comparisons = []
    for gap in hw['gaps']:
        mapped = (gap['aac_seconds'] - seconds,
                  gap['aac_seconds'] + gap['duration_ms'] / 1000 - seconds)
        a, b = max(replay_gaps, key=lambda g: overlap(mapped, (g[0] / sr, g[1] / sr)))
        fraction = overlap(mapped, (a / sr, b / sr)) / (mapped[1] - mapped[0])
        near = range(max(0, bisect_right(ready_ticks, dac_tick(a)) - 1),
                     min(len(packet_records), bisect_right(ready_ticks, dac_tick(b - 1)) + 1))
        context = [dict(replay_packet=i + 1, physical_sequence=packet_records[i]['sequence'],
            packet=packet_records[i]['packet'], command_quiet=voice_state(packet_records[i]['packet'])[1]) for i in near]
        comparisons.append(dict(physical=gap, mapped_replay_seconds=mapped,
            replay_gap=dict(first=a, last=b, first_seconds=a / sr, last_seconds=b / sr,
                            duration_ms=(b - a) * 1000 / sr),
            fixed_offset_overlap_fraction=fraction,
            overlap_at_offset_minus_plus_4ms=[overlap((mapped[0] + delta, mapped[1] + delta),
                (a / sr, b / sr)) / (mapped[1] - mapped[0]) for delta in (-.004, .004)],
            nearby_packets=context, dsp=register_context(writes, (a + b) // 2)))
    out.mkdir(parents=True, exist_ok=False)
    figures, players, clips = [], [], []
    for i, comparison in enumerate(comparisons):
        gap = comparison['physical']
        center = sum(comparison['mapped_replay_seconds']) / 2
        panels = (
            ('Physical raw FL (native)', raw, rr, 2147483648,
             (gap['first'] + gap['last']) / (2 * rr)),
            ('Replay FL (native, cold SPC)', simulated, sr, 32768, center))
        name = f'gap-{i}.svg'
        # Same fixed zoom for both sources and every gap, never fitted gain.
        (out / name).write_text(waveform_svg(panels, limit=.025))
        figures.append(f'<figure><img src="{name}"><figcaption>Gap {i}: fixed-offset silence overlap '
                       f'{comparison["fixed_offset_overlap_fraction"]:.1%}; waveform phases are not fitted. '
                       'Display axis is fixed at ±0.025 full scale for both sources; audio is unchanged.</figcaption></figure>')
        for label, pcm, rate, midpoint in (('physical', raw[:, :2], rr, (gap['first'] + gap['last']) // 2),
                                            ('replay', simulated, sr, int(center * sr))):
            start, end = max(0, midpoint - rate), min(len(pcm), midpoint + rate)
            name = f'gap-{i}-{label}.wav'; wavfile.write(out / name, rate, pcm[start:end])
            clips.append(dict(file=name, source=str(raw_path if label == 'physical' else normal / 'audio.wav'),
                              first=start, last=end, channels=[0, 1]))
            players.append(f'<p>Gap {i}, {label}: unchanged native samples<br><audio controls src="{name}"></audio></p>')
    report = dict(alignment=dict(**aligned, feature_step_seconds=STEP, offset_seconds=seconds,
        training_replay_seconds=TRAIN, training_hardware_aac_seconds=[t + seconds for t in TRAIN]),
        held_out=held, local_offset_sensitivity_not_applied=sensitivity, comparisons=comparisons,
        replay=dict(observer_neutral=onset['observer_neutral'], raw_dac_identical=onset['raw_dac_identical'],
                    received_packets=onset['received_packets'], wrong_first_pitch=onset['wrong_first_pitch'],
                    stale_nonzero_onsets=onset['stale_nonzero_onsets']), clips=clips,
        hardware_gaps_causally_resolved=False, sample_exact_alignment=False, pop_free_verified=False,
        scope=__doc__, sources={str(p): sha(p) for p in (Path(__file__),
            Path('tools/audit_pulse_onset.py'), Path('tools/audit_raw_monitor_audio.py'),
            Path('tools/audit_recorded_transients.py'), Path('tools/audit_dsp_latency.py'),
            Path('tools/analyze_game_silence.py'), hardware / 'report.json', audio_path,
            fixture / 'manifest.json', fixture / 'stream.bin', normal / 'report.json',
            observed / 'onset-observer.json', normal / 'audio.wav', raw_path)},
        artifacts={p.name: sha(p) for p in out.iterdir()})
    (out / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Same-command hardware gap replay</title>'
        '<style>body{max-width:1050px;margin:30px auto;background:#101821;color:#eee;font:18px system-ui}a{color:#9df}img{width:100%}audio{width:480px;max-width:100%}</style>'
        '<h1>Three hardware gaps: same-command replay</h1>'
        f'<p>All 1,238 hardware packets replayed and independently received byte-for-byte. A single {seconds:.3f}s '
        f'RMS-envelope offset is trained on replay 4..7s (correlation {aligned["training_correlation"]:.3f}). '
        'Those training samples exclude the three gap windows. Every held-out score and local-offset diagnostic is retained; no per-gap retiming.</p>'
        '<p>The replay produces silences near all three physical gaps, with nearby all-channel mute commands. '
        'The triangle deliberately releases its GAIN envelope while keeping nonzero volume registers; a volume-only mute check is insufficient. '
        'This supports commanded rests as an explanation, but cold initialization, unknown within-frame scheduling and imperfect alignment prevent a sample-exact hardware-cause verdict. '
        'It does not certify click-free audio or explain all reported sputtering.</p>' + ''.join(figures) + ''.join(players) +
        '<p><a href="report.json">All measurements, DSP writes, packet context and hashes</a> · '
        '<a href="../audio-packet-hardware-review-1690/">Original hardware trial</a></p>')
    report['artifacts']['index.html'] = sha(out / 'index.html')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), alignment=report['alignment'],
        overlaps=[r['fixed_offset_overlap_fraction'] for r in comparisons])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('fixture', 'normal', 'observed', 'hardware', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    audit(**vars(parser.parse_args()))
