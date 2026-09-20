"""Bind an exact game noise-table delta to route-neutral captures and sound stems."""
import argparse
import csv
import html
import json
import os
from pathlib import Path
import struct
import wave

import numpy as np

from tools.benchmark_report import sha, verify_capture
from tools.capture_audio_stem import options_for
from tools.prepare_audio import paired_engine, nearest_clock_engine
from tools.audit_stimulus_audio import metrics, verify_sources


def same_execution(left, right):
    if not left or len(left) != len(right):
        raise ValueError('Different/incomplete route lengths')
    for a, b in zip(left, right):
        if len(a.get('game_ram_hex', '')) != 4096 or len(b.get('game_ram_hex', '')) != 4096:
            raise ValueError('Missing full original-game RAM coverage')
        if {k: v for k, v in a.items() if k != 'audio'} != {k: v for k, v in b.items() if k != 'audio'}:
            raise ValueError(f'Non-audio execution changed at frame {a["frame"]}')
    return len(left)


def exact_patch(original, candidate, engine):
    if len(original) != 0x200000 or len(candidate) != len(original) or original.count(engine) != 1:
        raise ValueError('Unknown game/SPC image layout')
    start = original.index(engine)
    expected = bytearray(original)
    expected[start:start+len(engine)] = nearest_clock_engine(engine)
    expected[0xFFDC:0xFFE0] = b'\xff\xff\0\0'
    checksum = sum(expected) & 65535
    struct.pack_into('<HH', expected, 0xFFDC, checksum ^ 65535, checksum)
    if bytes(expected) != candidate:
        raise ValueError('Game changes extend beyond noise table/checksum')
    return dict(engine_offset=start, changed_offsets=[i for i, (a, b) in enumerate(zip(original, candidate)) if a != b])


def pcm(path):
    with wave.open(str(path)) as source:
        if source.getnchannels() != 2 or source.getsampwidth() != 2:
            raise ValueError('Need stereo PCM16')
        return source.getframerate(), np.frombuffer(source.readframes(source.getnframes()), '<i2').reshape(-1, 2)


def spectrum(samples, rate):
    x = samples[:, 0].astype(float)
    x -= x.mean()
    power = abs(np.fft.rfft(x*np.hanning(len(x))))**2
    total = power.sum()
    if total <= 0:
        raise ValueError('Unexpected silent selected noise frame')
    return float(np.sum(power*np.fft.rfftfreq(len(x), 1/rate))/total)


def noise_frames(bus, frames):
    updates = {}
    packet = []
    with bus.open() as source:
        for row in csv.reader(source):
            if row[0] != 'P':
                continue
            if int(row[5]) != len(packet):
                raise ValueError('Broken packet order')
            packet.append(int(row[6]))
            if len(packet) == 23:
                updates.setdefault(int(row[1]), []).append(tuple(packet))
                packet = []
    if packet:
        raise ValueError('Partial packet')
    current = (0,)*23
    states = []
    def key(p):
        return (p[14]&15, bool(p[21]&8) and bool(p[12]&16) and (p[12]&15) >= 2)
    for frame in range(1, frames+1):
        packets = updates.get(frame, [])
        keys = {key(current), *(key(p) for p in packets)}
        if packets:
            current = packets[-1]
        states.append(key(current) if len(keys) == 1 else None)
    # Stay away from clock/enable boundaries. Selection uses only register
    # state, not PCM similarity; changing software volume is retained.
    return [(i+1, states[i][0]) for i in range(2, frames-2)
            if states[i] is not None and states[i][1]
            and all(states[j] == states[i] for j in range(i-2, i+3))]


def audit(plan, out):
    paths = {key: Path(value) for key, value in plan.items()}
    names = ('baseline', 'candidate', 'baseline_noise', 'candidate_noise', 'baseline_rest', 'candidate_rest')
    captures = {name: verify_capture(paths[name]) for name in names}
    base, candidate = captures['baseline'], captures['candidate']
    frames = same_execution(base[1], candidate[1])
    for name in names:
        receipt, rows = captures[name]
        if not receipt['capture_complete'] or receipt['core_sha256'] != base[0]['core_sha256']:
            raise ValueError('Incomplete route or different audio core')
        if receipt['rom_sha256'] != captures['candidate' if name.startswith('candidate') else 'baseline'][0]['rom_sha256']:
            raise ValueError('Stem from a different cartridge')
        same_execution(base[1], rows)
        if name.endswith(('_noise', '_rest')):
            mode = 'noise' if name.endswith('_noise') else 'without-noise'
            stem = receipt.get('audio_stem', {})
            if (stem.get('mode') != mode or not stem.get('post_load_update_delivered') or
                    stem.get('wrapper_sha256') != sha(Path('tools/capture_audio_stem.py')) or
                    stem.get('options_queried') != {k.decode(): v.decode() for k, v in options_for('snes', mode).items()}):
                raise ValueError('Unbound or unapplied channel mask')
    for name in ('baseline', 'candidate'):
        if sha(paths[name+'_rom']) != captures[name][0]['rom_sha256']:
            raise ValueError('Wrong captured game ROM')
    engine = paired_engine(Path('.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes(), reset_notes=True, fast_reset=True)
    patch = exact_patch(paths['baseline_rom'].read_bytes(), paths['candidate_rom'].read_bytes(), engine)
    proofs = {name: verify_sources(paths[name+'_provenance']/'report.json') for name in ('baseline', 'candidate')}
    for name, proof in proofs.items():
        if proof['rom_sha256'] != captures[name][0]['rom_sha256'] or proof['audio_sha256'] != captures[name][0]['audio_sha256']:
            raise ValueError('SPC proof from different capture')
    trace_equality = {}
    for suffix in ('bus', 'keyon', 'synth', 'received'):
        traces = [[Path(p) for p in proofs[name]['sources'] if p.endswith('-'+suffix+'.csv')] for name in ('baseline', 'candidate')]
        if any(len(items) != 1 for items in traces):
            raise ValueError('Ambiguous SPC trace')
        trace_equality[suffix] = sha(traces[0][0]) == sha(traces[1][0])
    if not all(trace_equality.values()) or proofs['baseline']['sources'].get(str(paths['bus'])) != sha(paths['bus']):
        raise ValueError('Packet/SPC timing changed or unbound stimulus bus')
    nes = verify_sources(paths['nes']/'report.json')
    if (nes.get('audio_stem', {}).get('mode') != 'noise' or not nes['audio_stem'].get('post_load_update_delivered') or
            nes['timing'] != 'publication-frame' or nes['source_frames'] != frames or
            nes['sources'].get(str(paths['bus'])) != sha(paths['bus'])):
        raise ValueError('Wrong same-write NES noise reference')
    audio = {name: pcm(paths[name]/'audio.wav') for name in (*names, 'nes')}
    for name in names:
        if audio[name][0] != audio['baseline'][0] or len(audio[name][1]) != len(audio['baseline'][1]):
            raise ValueError('Different SNES sample count/rate')
    if not np.array_equal(audio['baseline_rest'][1], audio['candidate_rest'][1]):
        raise ValueError('Non-noise voices changed')
    for arm in ('baseline', 'candidate'):
        if any(np.array_equal(audio[arm][1], audio[arm+'_'+stem][1]) for stem in ('noise', 'rest')):
            raise ValueError('Channel isolation did not change the full mix')
        if not all(np.any(audio[arm+'_'+stem][1]) for stem in ('noise', 'rest')):
            raise ValueError('Dead isolated channel capture')
    if np.array_equal(audio['baseline_noise'][1], audio['candidate_noise'][1]):
        raise ValueError('Noise correction did not affect game output')
    nes_rows = json.loads((paths['nes']/'timeline.json').read_text())
    if [r['source_frame'] for r in nes_rows] != list(range(1, frames+1)):
        raise ValueError('Missing NES stimulus frames')
    selected = noise_frames(paths['bus'], frames)
    observations = []
    for frame, period in selected:
        observation = dict(frame=frame, period=period)
        for name in ('nes', 'baseline_noise', 'candidate_noise'):
            row = nes_rows[frame-1] if name == 'nes' else captures[name][1][frame-1]
            start = row['start_sample'] if name == 'nes' else row['audio_start_sample']
            end = row['end_sample'] if name == 'nes' else start+row['audio']['samples']
            trim = (end-start)//5
            observation[name] = spectrum(audio[name][1][start+trim:end-trim], audio[name][0])
        observations.append(observation)
    periods = []
    for period in sorted({r['period'] for r in observations}):
        rows = [r for r in observations if r['period'] == period]
        means = {name: float(np.mean([r[name] for r in rows])) for name in ('nes', 'baseline_noise', 'candidate_noise')}
        periods.append(dict(period=period, frames=len(rows), mean_centroids_hz=means,
                            absolute_distance_change_hz=abs(means['candidate_noise']-means['nes'])-abs(means['baseline_noise']-means['nes'])))
    if not observations:
        raise ValueError('No register-selected game noise frames')
    out.mkdir(parents=True, exist_ok=False)
    (out/'noise-frames.json').write_text(json.dumps(observations, indent=2)+'\n')
    park = [row for row in base[1] if row['phase'] == 'park_00_east_sweep'][:600]
    if len(park) != 600:
        raise ValueError('Missing fixed park audition segment')
    clips = {}
    for name in ('nes', 'baseline_noise', 'candidate_noise', 'baseline', 'candidate'):
        rows = nes_rows if name == 'nes' else captures[name][1]
        first, last = rows[park[0]['frame']-1], rows[park[-1]['frame']-1]
        start = first['start_sample'] if name == 'nes' else first['audio_start_sample']
        end = last['end_sample'] if name == 'nes' else last['audio_start_sample']+last['audio']['samples']
        path = out/(name+'-park.wav')
        with wave.open(str(path), 'wb') as target:
            target.setnchannels(2); target.setsampwidth(2); target.setframerate(audio[name][0])
            target.writeframes(audio[name][1][start:end].tobytes())
        clips[name] = dict(first_frame=park[0]['frame'], last_frame=park[-1]['frame'],
                           start_sample=start, end_sample=end, sha256=sha(path))
    report = dict(schema='rcr-noise-game-comparison-v1', passed=True, release_ready=False,
                  scope='Exact table-only ROM delta, unchanged whole-route non-audio telemetry and SPC delivery, identical non-noise PCM. Spectrum descriptive; not original-speed, pop-free, NES-fidelity or hardware certification.',
                  frames=frames, patch=patch, unchanged_spc_traces=trace_equality,
                  unmodified_park_clips=clips,
                  non_noise_pcm_identical=True, selected_noise_frames=len(observations), periods=periods,
                  full_mix={name: metrics(audio[name][1]) for name in ('baseline', 'candidate')})
    sources = [Path(__file__), Path('tools/prepare_audio.py'), Path('tools/capture_audio_stem.py'),
               Path('tools/audit_stimulus_audio.py'), Path('tools/benchmark_report.py'), out/'noise-frames.json']
    sources += [paths[name]/file for name in names for file in ('capture.json', 'timeline.json', 'audio.wav')]
    sources += [paths['nes']/file for file in ('report.json', 'timeline.json', 'audio.wav')]
    sources += [paths['baseline_rom'], paths['candidate_rom'], paths['bus']]
    sources += [paths[name+'_provenance']/'report.json' for name in ('baseline', 'candidate')]
    sources += [out/(name+'-park.wav') for name in clips]
    report['sources'] = {str(p): sha(p) for p in sources}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def rel(p):
        return html.escape(os.path.relpath(p, out))
    cards = ''.join(f'<section><h2>{html.escape(name.replace("_", " "))}</h2><audio controls src="{name}-park.wav"></audio><p>600 park frames, original PCM without normalization. <a href="{rel(paths[name]/"audio.wav")}">Full route</a></p></section>' for name in ('nes', 'baseline_noise', 'candidate_noise', 'baseline', 'candidate'))
    table = ''.join(f'<tr><td>{p["period"]}</td><td>{p["frames"]}</td>'+''.join(f'<td>{p["mean_centroids_hz"][n]:.0f}</td>' for n in ('nes', 'baseline_noise', 'candidate_noise'))+'</tr>' for p in periods)
    screenshots = ''.join(f'<section><h3>{arm}: frame {frame}</h3><img src="{rel(paths[arm]/captures[arm][1][frame-1]["frame_image"])}"></section>' for frame in (2400, 6000, 8000) for arm in ('baseline', 'candidate'))
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>In-game noise correction</title><style>body{font:16px system-ui;background:#111827;color:#e5efff;max-width:1100px;margin:30px auto}a{color:#8de5ff}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}section{background:#1c293e;padding:16px}audio,img{width:100%}img{image-rendering:pixelated}td,th{padding:8px}</style><h1>Game noise correction — not deployed</h1><p>'+report['scope']+'</p><p>'+str(frames)+' frames match outside audio. Non-noise sound is sample-identical. No speed or pop-free claim.</p><div class="grid">'+cards+'</div><h2>Register-selected noise frames</h2><p>Mean spectral centroids; not fundamental pitches. Same original APU writes at publication frames; not cycle-aligned. Different source clocks, filters and mixer.</p><table><tr><th>Period</th><th>Frames</th><th>NES Hz</th><th>Old SPC Hz</th><th>New SPC Hz</th></tr>'+table+'</table><h2>Identical captured frames</h2><div class="grid">'+screenshots+'</div><p><a href="report.json">Checks, hashes and limitations</a></p>')
    print(json.dumps({k: report[k] for k in ('passed', 'frames', 'selected_noise_frames', 'periods')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    audit(json.loads(args.plan.read_text()), args.out)
