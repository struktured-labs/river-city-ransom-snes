"""Executed NES/SPC noise sweep: audibility/mute/volume, not pop-free gameplay."""
import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import wave

import numpy as np

from tools import smoke_libretro as smoke
from tools.benchmark_capture import sha
from tools.prepare_audio import (paired_engine, nearest_clock_engine,
                                 NES_NOISE_PERIODS as NES_PERIODS,
                                 DSP_NOISE_DIVISORS as DSP_DIVISORS)
from tools.replay_nes_apu_stimulus import capture_player, pack_writes

ROOT = Path(__file__).resolve().parents[1]


def state(frame):
    phase = min(frame // 60, 19)
    return phase, (phase if phase < 16 else 15 if phase == 16 else 6), (0 if phase == 16 else 8), (0x3F if phase < 18 else 0x31 if phase == 18 else 0x30)


def stimulus():
    rows = []
    for frame in range(1, 1201):
        phase, period, enabled, volume = state(frame)
        if frame == 1 or frame % 60 == 0 and frame < 1200:
            writes = [(21, enabled), (12, volume), (14, period)]
            if frame in (1, 1020):
                writes.append((15, 0))  # enabled length reload
            for index, value in writes:
                rows.append(['W', str(frame), '0', '0', '0', str(index), str(value), '0'])
    return pack_writes(rows, 1200)


def measure_noise(pcm, rate, audible):
    pcm = np.asarray(pcm, dtype=float)
    if pcm.ndim != 2 or pcm.shape[1] != 2 or len(pcm) < rate // 2 or not np.isfinite(pcm).all():
        raise ValueError('Need at least half a second of finite stereo PCM')
    ac = pcm - pcm.mean(axis=0)
    rms = np.sqrt(np.mean(ac * ac, axis=0))
    width = round(rate * .01)
    blocks = pcm[:len(pcm)//width*width].reshape(-1, width, 2)
    local_ac = blocks - blocks.mean(axis=1, keepdims=True)
    activity = (np.sqrt(np.mean(local_ac**2, axis=1)) > 8).mean(axis=0)
    power = abs(np.fft.rfft(ac * np.hanning(len(ac))[:, None], axis=0))**2
    frequencies = np.fft.rfftfreq(len(ac), 1/rate)
    centroid = (power * frequencies[:, None]).sum(axis=0) / np.maximum(power.sum(axis=0), 1)
    clipping = float(np.mean(abs(pcm) >= 32767))
    peak = float(np.max(abs(pcm)))
    passed = (min(rms) > 16 and min(activity) >= .98 and clipping == 0) if audible else peak < 8
    return dict(passed=bool(passed), ac_rms=rms.tolist(), active_10ms_fraction=activity.tolist(),
                spectral_centroid_hz=centroid.tolist(), peak=peak, clipped_fraction=clipping)


def analyze(directory, system):
    with wave.open(str(directory/'audio.wav')) as source:
        rate = source.getframerate()
        if source.getnchannels() != 2 or source.getsampwidth() != 2:
            raise ValueError('Expected stereo signed 16-bit audio')
        pcm = np.frombuffer(source.readframes(source.getnframes()), '<i2').reshape(-1, 2)
    timeline = json.loads((directory/'timeline.json').read_text())
    key = 'driver_frame' if system == 'snes' else 'source_frame'
    phases, windows = [], []
    for phase in range(20):
        rows = [r for r in timeline if state(r[key])[0] == phase and r[key] <= 1200]
        expected_frames = list(range(max(1, phase*60), min(1201, (phase+1)*60)))
        if [r[key] for r in rows if r[key] < 1200] != expected_frames:
            raise ValueError('Missing/reordered phase frames')
        start = rows[0]['start_sample'] + round(rate*.15)
        end = rows[-1]['end_sample'] - round(rate*.15)
        window = pcm[start:end]
        result = measure_noise(window, rate, phase not in (16, 19))
        result.update(phase=phase, start_sample=start, end_sample=end)
        phases.append(result)
        windows.append(window)
    ratio = np.array(phases[17]['ac_rms']) / np.maximum(phases[18]['ac_rms'], 1)
    # Same period, 15:1 volume command. NES nonlinear mixing need not be 15:1.
    volume_passed = bool(np.all((ratio > 8) & (ratio < 22)))
    muted = windows[6]*0
    missing_right = windows[6].copy(); missing_right[:, 1] = 0
    dropout = windows[6].copy(); dropout[len(dropout)//2:len(dropout)//2+rate//10] = 0
    controls = dict(dead_capture=not measure_noise(muted, rate, True)['passed'],
                    dead_right=not measure_noise(missing_right, rate, True)['passed'],
                    dropout_100ms=not measure_noise(dropout, rate, True)['passed'],
                    audible_while_muted=not measure_noise(windows[6], rate, False)['passed'])
    return dict(phases=phases, volume_ratio=ratio.tolist(), volume_passed=volume_passed,
                synthetic_negative_controls=controls,
                passed=all(p['passed'] for p in phases) and volume_passed and all(controls.values()))


def capture_snes(core, out, nearest_clock=False):
    out.mkdir(parents=True, exist_ok=False)
    engine = paired_engine((ROOT/'.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes(), reset_notes=True, fast_reset=True)
    if nearest_clock:
        engine = nearest_clock_engine(engine)
    (out/'Memblers_2a03.bin').write_bytes(engine)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'), '-D', 'AUDIO_NOISE=1', '-D', 'AUDIO_PAIR=1',
                    '-D', 'AUDIO_RESET_NOTES=1', '-D', 'AUDIO_FAST_RESET=1', '--bin-include-dir', str(out),
                    '-o', str(out/'script.o'), str(ROOT/'snes/bringup.asm')], check=True)
    rom = out/'script.sfc'
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'), '-C', str(ROOT/'snes/lorom.cfg'),
                    '-o', str(rom), str(out/'script.o')], check=True)
    subprocess.run(['python3', str(ROOT/'tools/checksum.py'), str(rom)], check=True)
    original, retained, rows = C.CDLL, [], []
    total = 0

    def loader(path):
        nonlocal total
        lib = original(path)
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
            if ram[0xA22] == 0xEE:
                raise ValueError('SPC timeout')
            frame = int.from_bytes(ram[0xA20:0xA22], 'little')
            if ram[0xA22] == 1 and frame:
                phase, period, enabled, volume = state(frame)
                if (ram[0xA23], ram[0xA0E], ram[0xA15], ram[0xA0C]) != (phase, period, enabled, volume):
                    raise ValueError('Executed noise-register schedule differs')
                if any(ram[0xA00:0xA0C]) or any(ram[0xA10:0xA15]):
                    raise ValueError('Non-noise channel registers changed')
                rows.append(dict(driver_frame=frame, phase=phase, start_sample=start, end_sample=total))
        lib.retro_run = step
        return lib

    smoke.C.CDLL = loader
    try:
        receipt = smoke.run(core, rom, 1240, out/'audio.wav', kind='audio')
    finally:
        smoke.C.CDLL = original
    if [r['driver_frame'] for r in rows] != list(range(1, len(rows)+1)) or len(rows) < 1200:
        raise ValueError('Missing executed driver frames')
    if any(a['end_sample'] != b['start_sample'] for a, b in zip(rows, rows[1:])):
        raise ValueError('Noncontiguous sample telemetry')
    (out/'timeline.json').write_text(json.dumps(rows, indent=2)+'\n')
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')


def run(snes_core, nes_core, out, nearest_clock=False):
    out.mkdir(parents=True, exist_ok=False)
    capture_snes(snes_core, out/'snes', nearest_clock)
    nes = out/'nes'
    nes.mkdir()
    payload, grouped = stimulus()
    (nes/'stimulus.bin').write_bytes(payload)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'), '-D', 'SOURCE_FRAMES=1200',
                    '--bin-include-dir', str(nes), '-o', str(nes/'player.o'), str(ROOT/'snes/nes_apu_stimulus.asm')], check=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'), '-C', str(ROOT/'snes/nes_disabled_reload.cfg'),
                    '-o', str(nes/'player.nes'), str(nes/'player.o')], check=True)
    capture_player(nes_core, nes/'player.nes', nes, grouped)
    results = {system: analyze(out/system, system) for system in ('snes', 'nes')}
    sources = [Path(__file__), Path('tools/prepare_audio.py'), Path('tools/replay_nes_apu_stimulus.py'),
               Path('tools/smoke_libretro.py'), Path('snes/bringup.asm'), Path('snes/noise_script.inc'),
               Path('snes/native_spc_frame.inc'), Path('snes/nes_apu_stimulus.asm'),
               Path('snes/lorom.cfg'), Path('snes/nes_disabled_reload.cfg'), snes_core, nes_core,
               Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65')]
    sources += [p for system in ('snes', 'nes') for p in (out/system).iterdir() if p.suffix != '.o']
    report = dict(schema='rcr-noise-audio-v1', systems=results,
                  nearest_clock_experiment=nearest_clock,
                  scope='All 16 long-mode noise rates, mute, restart and constant volume on executed NES/SPC. Independent activity gates; spectra descriptive, not equivalence. No short-mode/envelope/length/gameplay/click-free verdict.',
                  passed=all(r['passed'] for r in results.values()), release_ready=False,
                  sources={str(p): sha(p) for p in sources})
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    table = ''.join(f'<tr><td>{i}</td><td>{results["nes"]["phases"][i]["spectral_centroid_hz"][0]:.0f}</td><td>{results["snes"]["phases"][i]["spectral_centroid_hz"][0]:.0f}</td></tr>' for i in range(16))
    verdict = 'PASS (isolated checks only)' if report['passed'] else 'FAIL — inspect phase gates; not release-ready'
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Noise channel audit</title><h1>NES / SPC noise channel</h1><h2>'+verdict+'</h2><p>'+report['scope']+'</p><h2>NES</h2><audio controls src="nes/audio.wav"></audio><h2>SNES</h2><audio controls src="snes/audio.wav"></audio><p>One second per rate 0–15, then disable, restart at rate 6, low volume, zero volume. Independent source clocks; no waveform alignment.</p><table><tr><th>Rate</th><th>NES centroid Hz</th><th>SPC centroid Hz</th></tr>'+table+'</table><p><a href="report.json">Measurements and hashes</a></p>')
    print(json.dumps(dict(passed=report['passed'], systems={k: v['passed'] for k, v in results.items()}, out=str(out))))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snes-core', type=Path, required=True)
    parser.add_argument('--nes-core', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--nearest-clock', action='store_true')
    args = parser.parse_args()
    raise SystemExit(0 if run(args.snes_core, args.nes_core, args.out, args.nearest_clock) else 1)
