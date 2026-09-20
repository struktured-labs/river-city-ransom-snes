"""Cycle-exact gameplay A/B audit for Memblers pulse-duty DSP key-ons."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import wave

import numpy as np
from PIL import Image, ImageDraw

try:
    from .analyze_audio_bus import analyze as analyze_bus
    from .benchmark_report import verify_capture, sha
except ImportError:
    from analyze_audio_bus import analyze as analyze_bus
    from benchmark_report import verify_capture, sha


DUTY_SITES = {0x04C5: 1, 0x05A7: 2}


def parse_keyons(rows):
    packets, startup, gameplay = 0, [], []
    for row in rows:
        if not row:
            raise ValueError('Empty key-on row')
        if row[0] == 'P':
            if len(row) != 7 or int(row[1]) != packets + 1:
                raise ValueError('Malformed or unordered packet marker')
            packets += 1
        elif row[0] == 'K':
            if len(row) != 4:
                raise ValueError('Malformed key-on marker')
            packet, value, pc = int(row[1]), int(row[2]), int(row[3], 16)
            if packet == 0:
                startup.append((value, pc))
            elif not 1 <= packet <= packets:
                raise ValueError('Key-on precedes its packet')
            else:
                gameplay.append(dict(packet=packet, voice_bits=value, pc=pc))
        else:
            raise ValueError('Unknown key-on row')
    if startup != [(0, 0x0BCB), (15, 0x0456)] or not packets:
        raise ValueError('Unexpected startup key-on sequence')
    return packets, gameplay


def synth_rows(rows):
    parsed = [(r[0], int(r[1]), int(r[2]), int(r[3], 16)) for r in rows]
    if any(kind not in ('P', 'R') for kind, *_ in parsed):
        raise ValueError('Unknown synthesis marker')
    return parsed


def load_pcm(root):
    with wave.open(str(root/'audio.wav')) as source:
        if source.getnchannels() != 2 or source.getsampwidth() != 2:
            raise ValueError('Need stereo PCM16')
        rate = source.getframerate()
        pcm = np.frombuffer(source.readframes(source.getnframes()), '<i2').reshape(-1, 2)
    return rate, pcm


def adjacent_metrics(pcm):
    delta = np.abs(np.diff(np.asarray(pcm, dtype=np.int32), axis=0))
    if not len(delta):
        raise ValueError('Need at least two PCM samples')
    return dict(max=int(delta.max()), rms=float(np.sqrt(np.mean(delta.astype(float)**2))),
                q99=float(np.quantile(delta, .99)), q999=float(np.quantile(delta, .999)),
                q9999=float(np.quantile(delta, .9999)))


def write_clip(path, rate, pcm):
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(2); out.setsampwidth(2); out.setframerate(rate)
        out.writeframes(np.asarray(pcm, dtype='<i2').tobytes())


def waveform(path, parent, candidate):
    width, height = 1200, 360
    image = Image.new('RGB', (width, height), (10, 17, 27))
    draw = ImageDraw.Draw(image)
    for samples, color, base in ((parent[:, 0], (35, 225, 245), 105),
                                 (candidate[:, 0], (255, 70, 205), 275)):
        peak = max(1, int(np.max(np.abs(samples))))
        index = np.linspace(0, len(samples)-1, width).astype(int)
        values = samples[index].astype(float)/peak*72
        draw.line([(x, base-int(y)) for x, y in enumerate(values)], fill=color, width=1)
        draw.line((0, base, width, base), fill=(70, 84, 105))
    draw.text((12, 12), 'parent (cyan), candidate (magenta); left channel; each independently scaled',
              fill=(230, 238, 250))
    image.save(path)


def non_audio_rows(rows):
    result = []
    for row in rows:
        copy = dict(row)
        copy.pop('audio', None); copy.pop('audio_start_sample', None)
        result.append(copy)
    return result


def audit(parent, candidate, parent_bus, candidate_bus, parent_keyon, candidate_keyon,
          parent_synth, candidate_synth, parent_engine, candidate_engine, out):
    verified = [verify_capture(root) for root in (parent, candidate)]
    for receipt, rows in verified:
        if (receipt['system'] != 'snes' or not receipt['capture_complete']
                or receipt['scenario_name'] != 'traversal-shop-exit'
                or any(r['fault'] for r in rows)):
            raise ValueError('Need complete fault-free SNES shop-exit captures')
    if verified[0][0]['scenario_sha256'] != verified[1][0]['scenario_sha256']:
        raise ValueError('Input scenarios differ')
    exact_game = non_audio_rows(verified[0][1]) == non_audio_rows(verified[1][1])

    with parent_bus.open() as source:
        parent_bus_report = analyze_bus(csv.reader(source), length_gate=True)
    with candidate_bus.open() as source:
        candidate_bus_report = analyze_bus(csv.reader(source), length_gate=True)
    if (parent_bus_report['mismatches'] or candidate_bus_report['mismatches']
            or parent_bus_report['unflushed_cpu_writes']
            or candidate_bus_report['unflushed_cpu_writes']):
        raise ValueError('Invalid CPU-to-SPC packet evidence')
    exact_bus = parent_bus.read_bytes() == candidate_bus.read_bytes()
    exact_packets = parent_bus_report['packets'] == candidate_bus_report['packets']

    with parent_keyon.open() as source:
        parent_packets, parent_events = parse_keyons(csv.reader(source))
    with candidate_keyon.open() as source:
        candidate_packets, candidate_events = parse_keyons(csv.reader(source))
    if (parent_packets != parent_bus_report['packet_count'] or candidate_packets != candidate_bus_report['packet_count']
            or any(e['pc'] not in DUTY_SITES or DUTY_SITES[e['pc']] != e['voice_bits'] for e in parent_events)):
        raise ValueError('Unexpected gameplay key-on evidence')
    if candidate_events:
        raise ValueError('Suppressed candidate still performs gameplay key-ons')

    with parent_synth.open() as source:
        p_synth = synth_rows(csv.reader(source))
    with candidate_synth.open() as source:
        c_synth = synth_rows(csv.reader(source))
    exact_synth = p_synth == c_synth

    p_engine, c_engine = parent_engine.read_bytes(), candidate_engine.read_bytes()
    changed = [i for i, pair in enumerate(zip(p_engine, c_engine)) if pair[0] != pair[1]]
    if len(p_engine) != len(c_engine) or changed != [0xC3, 0xC4, 0x1A5, 0x1A6]:
        raise ValueError('Engine A/B is not the checked four-byte substitution')
    for offset in (0xBF, 0x1A1):
        if (p_engine[offset:offset+6] not in (bytes.fromhex('8f4cf28f01f3'), bytes.fromhex('8f4cf28f02f3'))
                or c_engine[offset:offset+6] != bytes.fromhex('8f4cf28f0054')):
            raise ValueError('Engine key-on substitution preimage mismatch')

    rates_pcm = [load_pcm(root) for root in (parent, candidate)]
    if rates_pcm[0][0] != rates_pcm[1][0] or len(rates_pcm[0][1]) != len(rates_pcm[1][1]):
        raise ValueError('PCM shapes differ')
    rate = rates_pcm[0][0]
    packet_ids = sorted({e['packet'] for e in parent_events})
    frames = verified[0][1]
    events, cards = [], []
    out.mkdir(parents=True, exist_ok=False)
    for packet_id in packet_ids:
        packet = parent_bus_report['packets'][packet_id-1]
        frame = packet['frame']
        start_frame, end_frame = max(1, frame-1), min(len(frames), frame+2)
        start = frames[start_frame-1]['audio_start_sample']
        last = frames[end_frame-1]
        end = last['audio_start_sample'] + last['audio']['samples']
        p_clip, c_clip = rates_pcm[0][1][start:end], rates_pcm[1][1][start:end]
        base = f'packet-{packet_id:04d}'
        write_clip(out/f'{base}-parent.wav', rate, p_clip)
        write_clip(out/f'{base}-candidate.wav', rate, c_clip)
        waveform(out/f'{base}.png', p_clip, c_clip)
        voices = [e['voice_bits'] for e in parent_events if e['packet'] == packet_id]
        record = dict(packet=packet_id, raw_frame=frame, phase=frames[frame-1]['phase'],
                      voices=voices, sample_range=[start, end],
                      parent=adjacent_metrics(p_clip), candidate=adjacent_metrics(c_clip),
                      files=[f'{base}-parent.wav', f'{base}-candidate.wav', f'{base}.png'])
        events.append(record)
        cards.append(f'<details><summary>Packet {packet_id}, frame {frame}, {record["phase"]}, voices {voices}</summary>'
                     f'<img src="{base}.png"><div><audio controls src="{base}-parent.wav"></audio> parent '
                     f'<audio controls src="{base}-candidate.wav"></audio> candidate</div></details>')
    overall = dict(parent=adjacent_metrics(rates_pcm[0][1]),
                   candidate=adjacent_metrics(rates_pcm[1][1]))
    isolation = exact_game and exact_bus and exact_packets and exact_synth
    report = dict(schema='rcr-duty-keyon-game-audit-v1', experiment_valid=isolation,
                  release_ready=False, perceptual_audio_pass=None,
                  gates=dict(non_audio_timeline_identical=exact_game,
                             cpu_bus_trace_byte_identical=exact_bus,
                             packet_records_identical=exact_packets,
                             spc_synthesis_timing_identical=exact_synth,
                             candidate_gameplay_hard_keyons_removed=not candidate_events),
                  packet_count=parent_packets, cpu_write_count=parent_bus_report['cpu_writes'],
                  parent_gameplay_keyon_writes=len(parent_events),
                  candidate_gameplay_keyon_writes=len(candidate_events),
                  affected_packets=len(packet_ids), changed_engine_offsets=changed,
                  overall_adjacent_sample_metrics=overall, events=events,
                  hashes={str(path): sha(path) for path in (parent/'capture.json', candidate/'capture.json',
                         parent/'audio.wav', candidate/'audio.wav', parent_bus, candidate_bus,
                         parent_keyon, candidate_keyon, parent_synth, candidate_synth,
                         parent_engine, candidate_engine)},
                  scope='Cycle/size-exact four-byte SPC experiment; complete same-input route and mixed PCM. Valid isolation is not a perceptual no-pop or NES-fidelity verdict')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>RCR duty key-on A/B</title>'
        '<style>body{background:#0c121c;color:#eef5ff;font:16px system-ui;max-width:1250px;margin:auto;padding:24px}'
        'img{width:100%;background:#111}details{margin:14px 0;border:1px solid #43546b;padding:12px}summary{cursor:pointer}</style>'
        '<h1>Cycle-exact gameplay duty-key-on A/B</h1><p>The game, packet bus, and SPC schedule are identical. '
        'Only four engine bytes redirect two DSP KON data writes to unused scratch. This proves isolation, not audible correctness.</p>'
        f'<p>Parent: {len(parent_events)} gameplay hard key-ons. Candidate: {len(candidate_events)}. '
        f'Worst full-route adjacent sample: {overall["parent"]["max"]} → {overall["candidate"]["max"]}.</p>'
        '<p><a href="report.json">Machine-readable evidence and hashes</a></p>'+''.join(cards))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'candidate', 'parent-bus', 'candidate-bus', 'parent-keyon',
                 'candidate-keyon', 'parent-synth', 'candidate-synth', 'parent-engine',
                 'candidate-engine', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = vars(parser.parse_args())
    result = audit(**{key.replace('-', '_'): value for key, value in args.items()})
    print(json.dumps({key: result[key] for key in ('experiment_valid', 'packet_count',
          'cpu_write_count', 'parent_gameplay_keyon_writes', 'candidate_gameplay_keyon_writes',
          'affected_packets', 'overall_adjacent_sample_metrics')}, indent=2))
    raise SystemExit(0 if result['experiment_valid'] else 1)
