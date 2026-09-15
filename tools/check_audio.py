"""Executed SPC pulse/mute/restart/pitch tests; not full NES APU fidelity."""
import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import wave

import numpy as np

try:
    from . import smoke_libretro as smoke
    from .benchmark_capture import sha
    from .prepare_audio import prepare_engine
except ImportError:
    import smoke_libretro as smoke
    from benchmark_capture import sha
    from prepare_audio import prepare_engine

ROOT = Path(__file__).resolve().parents[1]


def measure(pcm, rate, expected_hz):
    samples = np.asarray(pcm, dtype=np.float64)
    if samples.ndim != 2 or samples.shape[1] != 2 or len(samples) < rate//4:
        raise ValueError('Need at least 250 ms of stereo PCM')
    ac = samples - samples.mean(axis=0)
    rms = np.sqrt(np.mean(ac*ac, axis=0))
    size = round(rate*.01)
    windows = ac[:len(ac)//size*size].reshape(-1, size, 2)
    activity = np.sqrt(np.mean(windows*windows, axis=1)) > 8
    frequencies = []
    for channel in range(2):
        spectrum = abs(np.fft.rfft(ac[:, channel]*np.hanning(len(ac))))
        frequency = np.fft.rfftfreq(len(ac), 1/rate)
        spectrum[(frequency < 50) | (frequency > 5000)] = 0
        frequencies.append(float(frequency[spectrum.argmax()]))
    clipped = float(np.mean(abs(samples) >= 32767))
    quiet_ms = []
    for channel in range(2):
        quiet = abs(ac[:, channel]) < 32
        edges = np.flatnonzero(np.diff(np.r_[False, quiet, False]))
        quiet_ms.append(float(max(edges[1::2]-edges[::2], default=0)*1000/rate))
    passed = (max(rms) < 8 and np.max(abs(samples)) < 8 if expected_hz is None else
              min(rms) > 128 and np.all(activity.mean(axis=0) >= .98)
              and all(abs(f-expected_hz) < expected_hz*.015 for f in frequencies)
              and clipped < .0001 and max(quiet_ms) <= .5)
    return {'passed': bool(passed), 'expected_hz': expected_hz,
            'dominant_hz': frequencies, 'ac_rms': rms.tolist(),
            'active_10ms_fraction': activity.mean(axis=0).tolist(), 'clipped_fraction': clipped,
            'longest_near_zero_ms': quiet_ms}


def measure_length(onset, tail, rate):
    onset = np.asarray(onset, dtype=float)
    if onset.ndim != 2 or onset.shape[1] != 2 or len(onset) < rate//50:
        raise ValueError('Need at least 20 ms of stereo onset PCM')
    result = measure(tail, rate, None)
    onset_rms = np.sqrt(np.mean((onset-onset.mean(axis=0))**2, axis=0))
    result['onset_ac_rms'] = onset_rms.tolist()
    result['passed'] = result['passed'] and bool(min(onset_rms) > 128)
    return result


def check(core, out, length=False, retrigger=False, sweep_reload=False, sweep_no_reload=False, triangle=False, unpatched_engine=False):
    if sum((length, retrigger, sweep_reload, sweep_no_reload, triangle)) > 1:
        raise ValueError('Audio probes are distinct profiles')
    out.mkdir(parents=True, exist_ok=False)
    original_engine = (ROOT/'.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes()
    engine = prepare_engine(original_engine)
    (out/'Memblers_2a03.bin').write_bytes(original_engine if unpatched_engine else engine)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'), '-D', 'AUDIO_SCRIPT=1',
                    *(['-D', 'AUDIO_LENGTH=1'] if length else []),
                    *(['-D', 'AUDIO_TRIANGLE=1'] if triangle else []),
                    *(['-D', 'AUDIO_RETRIGGER=1'] if retrigger else []),
                    *(['-D', 'AUDIO_SWEEP_RELOAD=1'] if sweep_reload or sweep_no_reload else []),
                    *(['-D', 'AUDIO_SWEEP_NO_RELOAD=1'] if sweep_no_reload else []),
                    '--bin-include-dir', str(out),
                    '-o', str(out/'script.o'), str(ROOT/'snes/bringup.asm')], check=True)
    rom = out/'script.sfc'
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'), '-C', str(ROOT/'snes/lorom.cfg'),
                    '-o', str(rom), str(out/'script.o')], check=True)
    subprocess.run(['python3', str(ROOT/'tools/checksum.py'), str(rom)], check=True)
    original_loader = C.CDLL
    retained, rows = [], []
    total = 0

    def loader(path):
        nonlocal total
        lib = original_loader(path)
        for name in ('retro_set_audio_sample_batch', 'retro_set_audio_sample'):
            setter = getattr(lib, name)
            def register(callback, setter=setter, batch=name.endswith('_batch')):
                @type(callback)
                def hooked(*args):
                    nonlocal total
                    result = callback(*args)
                    total += args[1] if batch else 1
                    return result
                retained.append(hooked)
                setter.argtypes = [type(callback)]
                setter(hooked)
            setattr(lib, name, register)
        run = lib.retro_run
        def step():
            start = total
            run()
            ram = C.string_at(lib.retro_get_memory_data(2), 8192)
            if ram[0xA22] == 1:
                rows.append({'phase': ram[0xA23], 'start_sample': start, 'end_sample': total,
                             'driver_frame': int.from_bytes(ram[0xA20:0xA22], 'little'),
                             'periodic_retriggers': ram[0xA24],
                             'channel_enable': ram[0xA15], 'triangle_control': ram[0xA08],
                             'triangle_period': ram[0xA0A] | ((ram[0xA0B] & 7) << 8),
                             'sweep_control': ram[0xA01], 'sweep_reloads': ram[0xA25]})
        lib.retro_run = step
        return lib

    smoke.C.CDLL = loader
    try:
        receipt = smoke.run(core, rom, 360, out/'audio.wav', kind='audio')
    finally:
        smoke.C.CDLL = original_loader
    with wave.open(str(out/'audio.wav')) as source:
        rate = source.getframerate()
        pcm = np.frombuffer(source.readframes(source.getnframes()), '<i2').reshape(-1, 2)
    if total != len(pcm) or sorted(set(r['phase'] for r in rows)) != [0, 1, 2, 3]:
        raise RuntimeError('Missing audio/phase coverage')
    if any(b['phase'] < a['phase'] or b['start_sample'] != a['end_sample'] for a,b in zip(rows, rows[1:])):
        raise RuntimeError('Non-contiguous audio phase telemetry')
    for row in rows:
        frame = row['driver_frame']
        if row['sweep_reloads'] != (frame % 256 if sweep_reload else 0):
            raise RuntimeError('Missing or unexpected sweep reload events')
        if frame and (sweep_reload or sweep_no_reload) and row['sweep_control'] != 0xF1:
            raise RuntimeError('Sweep probe did not enable sweep')
        expected_phase = 0 if frame < 120 else 1 if frame < 180 else 2 if frame < 240 else 3
        if row['phase'] != expected_phase:
            raise RuntimeError('Audio script changed phase at the wrong driver frame')
        if triangle and (row['channel_enable'] != (0 if expected_phase == 1 else 4)
                         or row['triangle_control'] != 255
                         or row['triangle_period'] != (126 if expected_phase == 3 else 253)):
            raise RuntimeError('Triangle probe register schedule is incorrect')
        if row['periodic_retriggers'] != (frame//32 if retrigger else 0):
            raise RuntimeError('Periodic retrigger execution does not match schedule')
    results = []
    for phase, expected in enumerate((1789773/(16*254), None, 1789773/(16*254), 1789773/(16*127))):
        if triangle and expected is not None:
            expected /= 2
        frames = [r for r in rows if r['phase'] == phase]
        start, end = frames[0]['start_sample']+rate//10, frames[-1]['end_sample']-rate//10
        result = measure(pcm[start:end], rate, expected)
        if length:
            # Ten half-frame clocks expire in about 83 ms on NTSC NES.
            # The late window begins after 100 ms and must be silent without
            # software muting. Also require an audible onset after retrigger.
            result = measure(pcm[start:end], rate, None)
            if phase != 1:
                onset = pcm[frames[0]['start_sample']+rate//100:
                            frames[0]['start_sample']+rate//20].astype(float)
                result = measure_length(onset, pcm[start:end], rate)
        result.update(phase=phase, start_sample=start, end_sample=end)
        results.append(result)
    (out/'timeline.json').write_text(json.dumps(rows, indent=2)+'\n')
    report = {'schema': 'rcr-spc-signal-test-v1', 'receipt': receipt,
              'scope': ('isolated sustained triangle, disable/restart/pitch; NOT linear-counter timing, NES mixing or game fidelity'
                        if triangle else
                        'controlled sweep period reload; NOT autonomous sweep timing, envelope, length, noise, DMC or game fidelity'
                        if sweep_reload or sweep_no_reload else
                        'pulse length-index-zero expiry and retrigger; NOT full frame-sequencer/envelope/sweep/noise/DMC or game fidelity'
                        if length else 'constant pulse, channel disable, restart, pitch change; NOT length/envelope/sweep/noise/DMC or game fidelity'),
              'profile': 'triangle-script' if triangle else ('sweep-no-reload' if sweep_no_reload else ('sweep-reload' if sweep_reload else ('length-expiry' if length else ('periodic-retrigger' if retrigger else 'pulse-script')))),
              'tool_sha256': sha(Path(__file__)), 'source_sha256': sha(ROOT/'snes/bringup.asm'),
              'spc_sha256': sha(out/'Memblers_2a03.bin'),
              'engine_patch_tool_sha256': sha(ROOT/'tools/prepare_audio.py'),
              'wav_sha256': sha(out/'audio.wav'), 'timeline_sha256': sha(out/'timeline.json'),
              'phases': results, 'passed': all(r['passed'] for r in results), 'release_ready': False}
    if sweep_reload:
        negative_out = out/'missing-reload'
        negative_passed = check(core, negative_out, sweep_no_reload=True)
        negative = json.loads((negative_out/'report.json').read_text())
        phases = negative['phases']
        if (negative_passed or not all(p['passed'] for p in phases[:3])
                or phases[3]['passed']
                or not all(abs(hz-440) < 10 for hz in phases[3]['dominant_hz'])
                or min(phases[3]['active_10ms_fraction']) < .98):
            raise RuntimeError('Missing reload did not reproduce the specific stale-pitch failure')
        report['negative_control'] = {'report_sha256': sha(negative_out/'report.json'),
                                      'expected_failure': 'phase 3 stays near 440 Hz instead of 880 Hz'}
    if triangle and not unpatched_engine:
        negative_out = out/'unpatched-engine'
        negative_passed = check(core, negative_out, triangle=True, unpatched_engine=True)
        negative = json.loads((negative_out/'report.json').read_text())
        if (negative_passed or not negative['phases'][1]['passed']
                or any(p['ac_rms'][0] < 128 or p['ac_rms'][1] != 0
                       for p in negative['phases'] if p['phase'] != 1)):
            raise RuntimeError('Unpatched engine did not reproduce left-only triangle')
        report['negative_control'] = {'report_sha256': sha(negative_out/'report.json'),
                                      'expected_failure': 'triangle absent on right output'}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    if triangle and not unpatched_engine:
        table = ''.join('<tr><td>'+str(p['phase'])+'</td><td>'+str(p['ac_rms'])+
                        '</td><td>'+str(negative['phases'][p['phase']]['ac_rms'])+'</td></tr>'
                        for p in results)
        (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Triangle output audit</title>'
            '<h1>Triangle output: corrected vs original engine</h1>'
            '<p>Isolated tone, disable, restart and pitch change. Not a full NES mix or gameplay verdict.</p>'
            '<h2>Corrected</h2><audio controls src="audio.wav"></audio>'
            '<h2>Original (right output missing)</h2><audio controls src="unpatched-engine/audio.wav"></audio>'
            '<table border="1"><tr><th>Phase</th><th>Corrected RMS [L,R]</th><th>Original RMS [L,R]</th></tr>'
            +table+'</table><p><a href="report.json">Verified measurements and hashes</a></p>')
    print(json.dumps(report, indent=2))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--length', action='store_true', help='Probe automatic NES pulse length expiry (currently unimplemented)')
    parser.add_argument('--retrigger', action='store_true', help='Probe periodic same-note retriggering and sub-millisecond dropouts')
    parser.add_argument('--sweep-reload', action='store_true', help='Probe repeated sweep period reload flags')
    parser.add_argument('--sweep-no-reload', action='store_true', help='Negative control: omit period reload while sweep is enabled')
    parser.add_argument('--triangle', action='store_true', help='Isolated sustained triangle, mute, restart and pitch probe')
    args = parser.parse_args()
    raise SystemExit(0 if check(args.core, args.out, args.length, args.retrigger, args.sweep_reload, args.sweep_no_reload, args.triangle) else 1)
