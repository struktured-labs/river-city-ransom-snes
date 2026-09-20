"""Bind acknowledged delivery gaps to full PCM and conservative review clips."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import wave
import numpy as np

try:
    from .analyze_spc_ack import analyze as analyze_ack
    from .analyze_audio_bus import analyze as analyze_bus
    from .benchmark_report import verify_capture, sha
except ImportError:
    from analyze_spc_ack import analyze as analyze_ack
    from analyze_audio_bus import analyze as analyze_bus
    from benchmark_report import verify_capture, sha


def nmi_coverage(packets, final_nmi):
    ids=[p['nmi'] for p in packets]
    if not ids or ids!=list(range(1,len(ids)+1)):
        raise ValueError('Expected exactly one ordered packet for each completed NMI')
    if final_nmi not in (len(ids),len(ids)+1):
        raise ValueError('Packet stream does not cover captured NMIs')
    return dict(completed_nmis=len(ids),final_nmi=final_nmi,
                unfinished_tail_nmi=final_nmi if final_nmi>len(ids) else None)


def build(capture, ack, bus, out, length_gate=False, paired=False, engine_size=None):
    receipt, rows = verify_capture(capture)
    if receipt['system'] != 'snes' or not receipt['capture_complete'] or any(r['fault'] for r in rows):
        raise ValueError('Need complete fault-free SNES capture')
    for key,path in (('spc_ack_trace',ack),('audio_bus_trace',bus)):
        if receipt.get(key,{}).get('sha256')!=sha(path):
            raise ValueError('Need capture-bound '+key+'; replay older unbound captures')
    acknowledgements = analyze_ack(csv.reader(ack.open()), paired=paired,
                                   engine_size=engine_size)
    packets = analyze_bus(csv.reader(bus.open()), length_gate=length_gate)
    if packets['mismatches'] or packets['packet_count'] != acknowledgements['acknowledged_packets']:
        raise ValueError('Packet mismatch or ACK count differs')
    coverage=nmi_coverage(packets['packets'],rows[-1]['nmi_counter'])
    # Cross-bind streams without assuming their trace files belong together.
    for packet, completed in zip(packets['packets'], acknowledgements['completions']):
        if packet['nmi'] != completed['nmi'] or not 0 <= completed['frame']-packet['frame'] <= 1:
            raise ValueError('Packet/ACK streams do not correspond')
    with wave.open(str(capture/'audio.wav')) as source:
        params = source.getparams()
        pcm = source.readframes(source.getnframes())
    width = params.nchannels * params.sampwidth
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(capture/'audio.wav', out/'full.wav')
    gaps = []
    html = ['<!doctype html><meta charset="utf-8"><title>Audio delivery gaps</title>',
            '<style>body{background:#121923;color:white;font:16px system-ui;max-width:1000px;margin:24px auto}audio{width:100%}</style>',
            '<h1>Audio delivery gaps</h1>',
            '<p>CPU-observed complete packet acknowledgements, not a click detector. Clips retain half a second on either side; raw core frames locate review windows only, not sample-exact DSP events.</p>',
            '<p>Full, unmodified stereo capture:</p><audio controls src="full.wav"></audio>']
    absolute_timing = acknowledgements['absolute_completion_timing']
    review_gaps = acknowledgements['gap_intervals']
    if absolute_timing is not None:
        review_gaps = []
        for interval in absolute_timing['long_intervals']:
            a, b = interval['before'], interval['after']
            review_gaps.append(dict(interval, video_frame_gap=
                b['frame'] + (b['line'] == 0) - a['frame'] - (a['line'] == 0)))
        html.append('<p>Clip selection uses measured intervals longer than 536049 master clocks '
                    '(1.5 nominal NTSC frames), not frame-number gaps. This is a review threshold, '
                    'not an audio-fidelity pass/fail gate.</p>')
    for index, gap in enumerate(review_gaps):
        first, last = gap['before']['frame'], gap['after']['frame']
        # Generous +/- one video-frame allowance around the raw-core frame
        # convention, plus 0.5 seconds of audible context. No phase alignment.
        lo, hi = max(0, first-2), min(len(rows)-1, last+1)
        start = max(0, rows[lo]['audio_start_sample']-params.framerate//2)
        end = min(params.nframes, rows[hi]['audio_start_sample']+params.framerate//2)
        filename = f'gap-{index:03d}.wav'
        with wave.open(str(out/filename), 'wb') as target:
            target.setparams(params)
            target.writeframes(pcm[start*width:end*width])
        item = dict(**gap, clip=filename, start_sample=start, end_sample=end,
                    nearby_phases=sorted({r['phase'] for r in rows[lo:hi+1]}),
                    clip_sha256=sha(out/filename))
        # Fixed interior, away from uncertain raw-frame origin and filter
        # onset: five frames after previous completion, two before next.
        # This measures retained sound, not the exact instant of a DSP event.
        inner_lo, inner_hi = first+5, last-2
        if 0 <= inner_lo < inner_hi < len(rows) and params.sampwidth == 2 and params.nchannels == 2:
            begin, finish = rows[inner_lo]['audio_start_sample'], rows[inner_hi]['audio_start_sample']
            values = np.frombuffer(pcm[begin*width:finish*width], '<i2').reshape(-1, 2).astype(float)
            if len(values):
                item['interior_pcm'] = dict(start_sample=begin, end_sample=finish,
                    ac_rms=np.sqrt(np.mean((values-values.mean(axis=0))**2, axis=0)).tolist(),
                    absolute_peak=float(np.max(abs(values))))
        gaps.append(item)
        html.append(f'<h2>Gap {gap["video_frame_gap"]} frames, raw frames {first}–{last}</h2>'
                    f'<p>Nearby phases: {", ".join(item["nearby_phases"])}</p>'
                    f'<audio controls src="{filename}"></audio>')
        if 'master_clocks' in gap:
            html.append(f'<p>Measured interval: {gap["master_clocks"]} master clocks '
                        f'({gap["master_clocks"]/357366:.3f} nominal NTSC frames). '
                        'Frame-number distance above is not elapsed duration.</p>')
        if 'interior_pcm' in item:
            html.append(f'<p>Fixed interior RMS [L,R]: {item["interior_pcm"]["ac_rms"]}; '
                        f'peak: {item["interior_pcm"]["absolute_peak"]}. Not a click verdict.</p>')
    report = dict(schema='rcr-audio-gap-audit-v1', release_ready=False,
                  nmi_coverage=coverage,
                  paired_transfer=paired, engine_size=engine_size,
                  absolute_completion_timing=acknowledgements['absolute_completion_timing'],
                  length_gate=length_gate, gated_packets=packets['gated_packets'],
                  capture_sha256=sha(capture/'capture.json'), ack_sha256=sha(ack),
                  bus_sha256=sha(bus), full_wav_sha256=sha(out/'full.wav'),
                  acknowledged_packets=acknowledgements['acknowledged_packets'],
                  gap_histogram=acknowledgements['completion_frame_gap_histogram'],
                  unflushed_cpu_writes=packets['unflushed_cpu_writes'], gaps=gaps,
                  scope='Delivery cadence plus reviewable PCM; no asserted perceptual click or DSP event alignment')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'index.html').write_text('\n'.join(html)+'<p><a href="report.json">Hash-bound report</a></p>')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--length-gate', action='store_true')
    parser.add_argument('--paired', action='store_true')
    parser.add_argument('--engine-size', type=lambda value: int(value, 0),
                        help='Uploaded SPC byte count for ACK stream activation')
    for name in ('capture', 'ack', 'bus', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    build(args.capture, args.ack, args.bus, args.out, length_gate=args.length_gate,
          paired=args.paired, engine_size=args.engine_size)
