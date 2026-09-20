"""Bound mixed-gameplay PCM discontinuities at observed SPC key-on packets.

This audit deliberately separates three claims: CPU/SPC transport correctness,
continuous emulator audio callbacks, and a digital discontinuity bound.  It is
not a psychoacoustic or analog-capture verdict.
"""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import shutil
import wave

import numpy as np

try:
    from .analyze_audio_bus import analyze as analyze_bus
    from .analyze_game_keyons import analyze as analyze_keyons
    from .benchmark_report import verify_capture
    from .audit_spc_event_provenance import splash_ident_model, validate_bindings
except ImportError:
    from analyze_audio_bus import analyze as analyze_bus
    from analyze_game_keyons import analyze as analyze_keyons
    from benchmark_report import verify_capture
    from audit_spc_event_provenance import splash_ident_model, validate_bindings


FULL_SCALE = 32768.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_timeline(rows, pcm_samples, capture_frames):
    if len(rows) != capture_frames or not rows:
        raise ValueError('Timeline/capture frame count mismatch')
    expected_start = 0
    for expected_frame, row in enumerate(rows, 1):
        samples = row.get('audio', {}).get('samples')
        if (row.get('frame') != expected_frame or row.get('audio_start_sample') != expected_start
                or not isinstance(samples, int) or samples <= 0):
            raise ValueError('Missing, reordered or discontinuous audio callback')
        expected_start += samples
    if expected_start != pcm_samples:
        raise ValueError('Timeline does not cover the complete waveform')
    return dict(frames=len(rows), samples=expected_start,
                minimum_callback_samples=min(row['audio']['samples'] for row in rows),
                maximum_callback_samples=max(row['audio']['samples'] for row in rows))


def parse_keyon_packets(rows):
    """Return packet-level reset/duty events using the same state as the audit."""
    old_duty = [0, 0]
    packets = []
    expected_number = 1
    for row in rows:
        if not row or row[0] != 'P':
            continue
        if len(row) != 7:
            raise ValueError('Malformed key-on packet row')
        number, reset, enable, control0, control1 = map(int, row[1:6])
        if number != expected_number:
            raise ValueError('Non-contiguous key-on packet numbers')
        expected_number += 1
        reset_bits = reset & enable & 3
        duty_bits = 0
        for channel, control in enumerate((control0, control1)):
            bit = 1 << channel
            if enable & bit:
                duty = control >> 6
                if duty != old_duty[channel]:
                    duty_bits |= bit
                old_duty[channel] = duty
        if reset_bits or duty_bits:
            packets.append(dict(packet=number, reset_bits=reset_bits, duty_bits=duty_bits,
                                keyon_bits=reset_bits | duty_bits))
    if expected_number == 1:
        raise ValueError('No key-on packets')
    return packets, expected_number - 1


def correlate_events(keyon_rows, bus_packets, timeline):
    events, packet_count = parse_keyon_packets(keyon_rows)
    if packet_count != len(bus_packets):
        raise ValueError('Key-on and bus packet counts differ')
    by_frame = {}
    for event in events:
        publication = bus_packets[event['packet'] - 1]
        frame = publication['frame']
        if not 1 <= frame <= len(timeline):
            raise ValueError('Packet publication falls outside capture')
        target = by_frame.setdefault(frame, dict(frame=frame, packets=[], reset_bits=0,
                                                  duty_bits=0, keyon_bits=0))
        target['packets'].append(event['packet'])
        for field in ('reset_bits', 'duty_bits', 'keyon_bits'):
            target[field] |= event[field]
    if not by_frame:
        raise ValueError('No gameplay key-on events')
    return list(by_frame.values()), len(events), packet_count


def _frame_measure(pcm, row):
    start = row['audio_start_sample']
    end = start + row['audio']['samples']
    first = max(0, start - 1)
    segment = pcm[first:end].astype(np.int64)
    steps = np.abs(np.diff(segment, axis=0))
    maximum = int(steps.max()) if len(steps) else 0
    where = np.unravel_index(int(np.argmax(steps)), steps.shape) if len(steps) else (0, 0)
    sample = int(first + where[0] + 1)
    return dict(max_step=maximum, max_step_to_full_scale=maximum / FULL_SCALE,
                max_step_sample=sample, max_step_channel=int(where[1]))


def measure(pcm, timeline, events):
    if pcm.ndim != 2 or pcm.shape[1] != 2 or len(pcm) < 2:
        raise ValueError('Need nonempty stereo PCM')
    event_by_frame = {event['frame']: event for event in events}
    frames = []
    for row in timeline:
        item = dict(frame=row['frame'], phase=row['phase'], event=row['frame'] in event_by_frame,
                    **_frame_measure(pcm, row))
        if item['event']:
            item.update({key: value for key, value in event_by_frame[row['frame']].items()
                         if key != 'frame'})
        frames.append(item)
    all_steps = np.abs(np.diff(pcm.astype(np.int64), axis=0))
    maximum = int(all_steps.max())
    event_frames = [row for row in frames if row['event']]
    phase_rows = {}
    for row in frames:
        phase = phase_rows.setdefault(row['phase'], {'frames': 0, 'event_frames': 0,
                                                      'max_step': 0, 'event_max_step': 0})
        phase['frames'] += 1
        phase['max_step'] = max(phase['max_step'], row['max_step'])
        if row['event']:
            phase['event_frames'] += 1
            phase['event_max_step'] = max(phase['event_max_step'], row['max_step'])
    for phase in phase_rows.values():
        phase['max_step_to_full_scale'] = phase['max_step'] / FULL_SCALE
        phase['event_max_step_to_full_scale'] = phase['event_max_step'] / FULL_SCALE
    return dict(samples=len(pcm), absolute_peak=int(np.abs(pcm.astype(np.int64)).max()),
                clipped_samples=int(np.count_nonzero(np.abs(pcm.astype(np.int64)) >= 32767)),
                max_step=maximum, max_step_to_full_scale=maximum / FULL_SCALE,
                event_max_step=max(row['max_step'] for row in event_frames),
                event_max_step_to_full_scale=max(row['max_step_to_full_scale'] for row in event_frames),
                event_frames=len(event_frames), phases=phase_rows, frames=frames)


def evaluate(measurement, reference_limit):
    return [
        dict(gate='complete_audio_callbacks', passed=True,
             candidate='validated before measurement', limit='one positive contiguous callback per frame'),
        dict(gate='pcm_clipping', passed=measurement['clipped_samples'] == 0,
             candidate=measurement['clipped_samples'], limit=0),
        dict(gate='whole_capture_discontinuity',
             passed=measurement['max_step_to_full_scale'] <= reference_limit,
             candidate=measurement['max_step_to_full_scale'], limit=reference_limit),
        dict(gate='keyon_frame_discontinuity',
             passed=measurement['event_max_step_to_full_scale'] <= reference_limit,
             candidate=measurement['event_max_step_to_full_scale'], limit=reference_limit),
    ]


def _load_pcm(path):
    with wave.open(str(path)) as source:
        if source.getnchannels() != 2 or source.getsampwidth() != 2:
            raise ValueError('Need stereo PCM16')
        rate = source.getframerate()
        pcm = np.frombuffer(source.readframes(source.getnframes()), '<i2').reshape(-1, 2)
    return pcm, rate


def _reference(root):
    report_path = root / 'report.json'
    audio_path = root / 'nes.wav'
    report = json.loads(report_path.read_text())
    if (report.get('schema') != 'rcr-retrigger-transient-audit-v1' or not report.get('passed')
            or not all(case.get('rejected') for case in report.get('sensitivity_controls', {}).values())):
        raise ValueError('Reference transient audit is not a passing fail-sensitive audit')
    variant = report.get('variants', {}).get('nes', {})
    if sha(audio_path) != variant.get('wav_sha256'):
        raise ValueError('Executed NES reference waveform hash mismatch')
    pcm, rate = _load_pcm(audio_path)
    global_step = int(np.abs(np.diff(pcm.astype(np.int64), axis=0)).max()) / FULL_SCALE
    event_step = variant.get('max_step_to_full_scale')
    limit = report.get('limits', {}).get('max_step_to_full_scale')
    if not (isinstance(event_step, (int, float)) and isinstance(limit, (int, float))
            and 0 < event_step <= limit < 1 and global_step >= event_step):
        raise ValueError('Invalid executed NES transient bound')
    return dict(report_sha256=sha(report_path), wav_sha256=sha(audio_path), sample_rate=rate,
                event_max_step_to_full_scale=event_step,
                global_max_step_to_full_scale=global_step, limit=limit)


def _sensitivity_controls(pcm, timeline, events, reference_limit):
    first = timeline[events[0]['frame'] - 1]
    spike = pcm.copy()
    at = first['audio_start_sample'] + min(2, first['audio']['samples'] - 2)
    spike[at] = -32768
    spike[at + 1] = 32767
    spike_measurement = measure(spike, timeline, events)
    spike_gates = evaluate(spike_measurement, reference_limit)
    broken = [dict(row) for row in timeline]
    broken[events[0]['frame'] - 1] = dict(broken[events[0]['frame'] - 1],
                                           audio=dict(broken[events[0]['frame'] - 1]['audio'], samples=0))
    try:
        validate_timeline(broken, len(pcm), len(timeline))
        missing_rejected = False
    except ValueError:
        missing_rejected = True
    return {
        'full_scale_spike': dict(rejected=not all(gate['passed'] for gate in spike_gates),
                                 gates=spike_gates),
        'missing_audio_callback': dict(rejected=missing_rejected),
    }


def _svg(pcm, sample, peak):
    lo, hi = max(0, sample - 320), min(len(pcm), sample + 320)
    values = pcm[lo:hi, 0].astype(float)
    points = ' '.join(f'{index * 640 / max(1, len(values)-1):.2f},{70 - value * 58 / max(1, peak):.2f}'
                      for index, value in enumerate(values))
    marker = (sample - lo) * 640 / max(1, len(values)-1)
    return (f'<svg viewBox="0 0 640 140"><polyline fill="none" stroke="#55e6ff" points="{points}"/>'
            f'<line x1="{marker:.2f}" y1="0" x2="{marker:.2f}" y2="140" stroke="#ff4ea3"/></svg>')


def _write_clip(path, pcm, rate, center):
    radius = round(rate * .35)
    lo, hi = max(0, center - radius), min(len(pcm), center + radius)
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm[lo:hi].astype('<i2').tobytes())


def audit(capture, keyon_trace, keyon_report_path, bus_trace, bus_report_path,
          reference_audit, out):
    out.mkdir(parents=True, exist_ok=False)
    receipt_path, timeline_path, wav_path = capture/'capture.json', capture/'timeline.json', capture/'audio.wav'
    receipt, timeline = verify_capture(capture)
    if (receipt.get('schema') != 'rcr-benchmark-capture-v1' or receipt.get('system') != 'snes'
            or not receipt.get('capture_complete') or any(r['fault'] for r in timeline)
            or not receipt.get('scenario_name', '').startswith('traversal')):
        raise ValueError('Need a complete SNES traversal capture')
    if sha(timeline_path) != receipt.get('timeline_sha256') or sha(wav_path) != receipt.get('audio_sha256'):
        raise ValueError('Capture hash mismatch')
    validate_bindings(receipt, dict(game_keyon_trace=keyon_trace, audio_bus_trace=bus_trace))
    pcm, rate = _load_pcm(wav_path)
    coverage = validate_timeline(timeline, len(pcm), receipt['frames'])
    if rate != round(receipt['sample_rate']):
        raise ValueError('Capture audio rate mismatch')

    keyon_report = json.loads(keyon_report_path.read_text())
    bus_report = json.loads(bus_report_path.read_text())
    if sha(keyon_trace) != keyon_report.get('trace_sha256') or sha(bus_trace) != bus_report.get('trace_sha256'):
        raise ValueError('Trace/report hash mismatch')
    with keyon_trace.open() as source:
        keyon_rows = list(csv.reader(source))
    checked_keyons = analyze_keyons(keyon_rows, fast=True,
                                    splash_ident=splash_ident_model(capture, receipt))
    with bus_trace.open() as source:
        checked_bus = analyze_bus(csv.reader(source), length_gate=True)
    if (not checked_keyons['passed'] or not keyon_report.get('passed') or keyon_report.get('schedule') != 'fast'
            or keyon_report.get('transport') != 'paired' or keyon_report.get('mismatch_count')
            or checked_keyons['expected_keyon_writes'] != keyon_report.get('expected_keyon_writes')
            or checked_keyons['packets'] != keyon_report.get('packets')):
        raise ValueError('Key-on schedule is not the passing fast paired schedule')
    if (bus_report.get('mismatches') or bus_report.get('unflushed_cpu_writes')
            or checked_bus['mismatches'] or checked_bus['unflushed_cpu_writes']
            or checked_bus['packet_count'] != bus_report.get('packet_count')):
        raise ValueError('Audio bus transport is not lossless')

    events, event_packets, packet_count = correlate_events(keyon_rows, checked_bus['packets'], timeline)
    measurement = measure(pcm, timeline, events)
    reference = _reference(reference_audit)
    gates = evaluate(measurement, reference['limit'])
    controls = _sensitivity_controls(pcm, timeline, events, reference['limit'])
    passed = all(gate['passed'] for gate in gates) and all(case['rejected'] for case in controls.values())

    ranked = sorted((row for row in measurement['frames'] if row['event']),
                    key=lambda row: row['max_step'], reverse=True)[:20]
    shutil.copyfile(wav_path, out/'full.wav')
    cards, table_rows = [], []
    for index, row in enumerate(ranked, 1):
        filename = f'event-{index:02d}-frame-{row["frame"]}.wav'
        _write_clip(out/filename, pcm, rate, row['max_step_sample'])
        seconds = row['max_step_sample'] / rate
        packet_text = ', '.join(map(str, row['packets']))
        table_rows.append(
            f'<tr><td>{index}</td><td>{row["frame"]}</td><td>{html.escape(row["phase"])}</td>'
            f'<td>{packet_text}</td><td>{row["max_step"]}</td><td>{row["max_step_to_full_scale"]:.6f}</td>'
            f'<td><button data-seek="{seconds:.6f}">seek full recording</button></td></tr>')
        cards.append(f'<section><h3>#{index}: frame {row["frame"]} · {html.escape(row["phase"])}</h3>'
                     f'<p>Packets {packet_text}; reset bits {row["reset_bits"]}; duty bits {row["duty_bits"]}; '
                     f'maximum adjacent-sample step {row["max_step"]}.</p>'
                     f'<audio controls src="{filename}"></audio>{_svg(pcm, row["max_step_sample"], measurement["absolute_peak"])}</section>')
    compact_frames = [{key: row[key] for key in ('frame', 'phase', 'event', 'max_step',
                                                   'max_step_to_full_scale', 'max_step_sample')}
                      | ({key: row[key] for key in ('packets', 'reset_bits', 'duty_bits', 'keyon_bits')}
                         if row['event'] else {}) for row in measurement.pop('frames')]
    result = dict(
        schema='rcr-gameplay-transient-audit-v1', passed=passed, release_ready=False,
        implementation_sources={str(p):sha(p) for p in (Path(__file__),
            Path('tools/benchmark_report.py'), Path('tools/audit_spc_event_provenance.py'),
            Path('tools/analyze_game_keyons.py'), Path('tools/analyze_audio_bus.py'))},
        capture=dict(path=str(capture), report_sha256=sha(receipt_path), audio_sha256=sha(wav_path),
                     timeline_sha256=sha(timeline_path), rom_sha256=receipt['rom_sha256'],
                     scenario=receipt['scenario_name'], frames=receipt['frames'], sample_rate=rate),
        sources=dict(keyon_trace_sha256=sha(keyon_trace), keyon_report_sha256=sha(keyon_report_path),
                     bus_trace_sha256=sha(bus_trace), bus_report_sha256=sha(bus_report_path)),
        transport=dict(packets=packet_count, keyon_event_packets=event_packets,
                       expected_keyon_writes=checked_keyons['expected_keyon_writes'],
                       mismatches=0, unflushed_cpu_writes=0),
        callback_coverage=coverage, executed_nes_reference=reference,
        measurement=measurement, gates=gates, sensitivity_controls=controls,
        ranked_event_frames=compact_frames,
        near_zero_policy=('Near-zero runs are reported by the isolated retrigger audit, not gated here: mixed game music intentionally contains silent frames and room-load silences. Packet ACK/cadence evidence covers delivery gaps.'),
        scope=('Complete mixed PCM from one deterministic shop-and-mall traversal. Correlates every observed pulse reset/duty key-on packet to its publication frame and bounds adjacent-sample discontinuities against an executed isolated NES retrigger. Not a psychoacoustic verdict, waveform-equivalence score, analog MiSTer measurement, or proof that no listener can hear a pop.'))
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    gate_rows = ''.join(f'<tr><td>{html.escape(g["gate"])}</td><td>{g["passed"]}</td><td>{html.escape(str(g["candidate"]))}</td><td>{html.escape(str(g["limit"]))}</td></tr>' for g in gates)
    (out/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>RCR mixed-gameplay audio audit</title>'
        '<style>body{background:#0d1117;color:#e6edf3;font:16px system-ui;max-width:1180px;margin:24px auto;padding:0 16px}'
        'a{color:#55e6ff}table{border-collapse:collapse;width:100%}td,th{border:1px solid #46515e;padding:.45em;text-align:left}'
        'section{border-top:1px solid #46515e;padding:12px 0}audio{width:100%}svg{width:100%;height:180px;background:#151b23}'
        'button{background:#243447;color:white;border:1px solid #55e6ff;padding:.3em .6em}</style>'
        '<h1>Mixed-gameplay key-on/transient audit</h1>'
        '<p><strong>Unmodified complete recording:</strong></p><audio id="full" controls src="full.wav"></audio>'
        '<p>This fail-closed audit binds the capture, packet traces, callback timeline, executed NES bound, and negative controls. '
        'It measures digital discontinuities; it does not claim subjective inaudibility or replace a MiSTer analog recording.</p>'
        '<p><a href="report.json">Full measurements, hashes, per-phase results, and sensitivity controls</a></p>'
        f'<h2>Gates</h2><table><tr><th>Gate</th><th>Pass</th><th>Candidate</th><th>Limit</th></tr>{gate_rows}</table>'
        f'<h2>20 strongest key-on frames</h2><table><tr><th>Rank</th><th>Frame</th><th>Phase</th><th>Packets</th><th>Step</th><th>Full scale</th><th>Listen</th></tr>{"".join(table_rows)}</table>'
        + ''.join(cards)
        + '<script>const audio=document.querySelector("#full");document.querySelectorAll("button[data-seek]").forEach(b=>b.onclick=()=>{audio.currentTime=+b.dataset.seek;audio.play()})</script>')
    print(json.dumps(dict(passed=passed, gates=gates, packets=packet_count,
                          keyon_event_packets=event_packets, event_frames=measurement['event_frames'],
                          sensitivity_controls={key: value['rejected'] for key, value in controls.items()}), indent=2))
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--keyon-trace', type=Path, required=True)
    parser.add_argument('--keyon-report', type=Path, required=True)
    parser.add_argument('--bus-trace', type=Path, required=True)
    parser.add_argument('--bus-report', type=Path, required=True)
    parser.add_argument('--reference-audit', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if audit(args.capture, args.keyon_trace, args.keyon_report,
                                args.bus_trace, args.bus_report, args.reference_audit, args.out) else 1)
