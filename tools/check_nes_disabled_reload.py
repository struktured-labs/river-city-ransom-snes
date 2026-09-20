"""Execute ordered disable/reload/re-enable writes on an NES core."""
import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import wave
import numpy as np

try:
    from . import smoke_libretro as smoke
    from .check_audio import measure, sha
except ImportError:
    import smoke_libretro as smoke
    from check_audio import measure, sha

ROOT = Path(__file__).resolve().parents[1]


def pulse_periodicity(pcm, rate, hz):
    """Check full-period recurrence and reject octave-up ambiguity."""
    values = np.asarray(pcm, dtype=float)
    values = values - values.mean(axis=0)
    period = rate / hz
    def correlation(lag):
        a, b = values[:-lag], values[lag:]
        denominator = np.sqrt(np.sum(a*a, axis=0)*np.sum(b*b, axis=0))
        return np.divide(np.sum(a*b, axis=0), denominator,
                         out=np.zeros(2), where=denominator > 0)
    lags = range(max(1, int(period*.985)), int(period*1.015)+2)
    best = max(lags, key=lambda lag: float(min(correlation(lag))))
    full = correlation(best)
    half = correlation(max(1, round(best/2)))
    return dict(passed=bool(min(full) > .9 and max(half) < .8),
                lag_samples=best, full_period_correlation=full.tolist(),
                half_period_correlation=half.tolist())


def check(core, out, retrigger=False, suppress_retriggers=False, pulse2=False):
    if pulse2 and not retrigger:
        raise ValueError('Pulse-2 reference requires retrigger profile')
    if suppress_retriggers and not retrigger:
        raise ValueError('Suppression requires retrigger profile')
    out.mkdir(parents=True, exist_ok=False)
    source = ROOT/'snes/nes_disabled_reload.asm'
    config = ROOT/'snes/nes_disabled_reload.cfg'
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),
                    *(['-D', 'NES_RETRIGGER=1'] if retrigger else []),
                    *(['-D', 'NES_PULSE2=1'] if pulse2 else []),
                    *(['-D', 'NES_NO_RETRIGGER=1'] if suppress_retriggers else []),
                    '-o', str(out/'probe.o'), str(source)], check=True)
    rom = out/'probe.nes'
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'), '-C', str(config), '-o', str(rom), str(out/'probe.o')], check=True)
    original = C.CDLL
    rows, retained = [], []
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
            if lib.retro_get_memory_size(2) != 2048:
                raise RuntimeError('Expected original NES RAM')
            ram = C.string_at(lib.retro_get_memory_data(2), 2048)
            if ram[0x203] == 1:
                rows.append(dict(driver_frame=int.from_bytes(ram[0x200:0x202], 'little'),
                                 phase=ram[0x202], length_active=ram[0x204],
                                 periodic_retriggers=ram[0x205] if retrigger else None,
                                 start_sample=start, end_sample=total))
        lib.retro_run = step
        return lib
    smoke.C.CDLL = loader
    try:
        # Generic callback capture; NES-specific RAM/PCM gates are below.
        receipt = smoke.run(core, rom, 360, out/'audio.wav', kind='render')
    finally:
        smoke.C.CDLL = original
    with wave.open(str(out/'audio.wav')) as f:
        rate = f.getframerate()
        pcm = np.frombuffer(f.readframes(f.getnframes()), '<i2').reshape(-1, 2)
    if len(pcm) != total or set(r['phase'] for r in rows) != {0,1,2,3}:
        raise RuntimeError('Incomplete audio/phase capture')
    phases = []
    if retrigger and any(r['periodic_retriggers'] != r['driver_frame']//32 for r in rows):
        raise RuntimeError('Original NES periodic reset schedule differs')
    for phase, hz in enumerate((1789773/(16*254), None, 1789773/(16*254), 1789773/(16*127))):
        segment = [r for r in rows if r['phase'] == phase]
        expected_active = (2 if pulse2 else 1) if phase != 1 else 0
        stable = [r for r in segment if r['driver_frame'] > segment[0]['driver_frame']+2]
        if not stable or any(r['length_active'] != expected_active for r in stable):
            raise RuntimeError('NES length state differs from ordered-write expectation')
        start = segment[0]['start_sample']+rate//10
        end = segment[-1]['end_sample']-rate//10
        result = measure(pcm[start:end], rate, hz)
        if retrigger and hz is not None:
            # A narrow NES pulse can have a stronger second harmonic after
            # filtering. Preserve its FFT result, but independently verify
            # recurrence at the fundamental and reject octave-up ambiguity.
            recurrence = pulse_periodicity(pcm[start:end], rate, hz)
            result['fft_tone_gate_passed'] = result['passed']
            result['fundamental_periodicity'] = recurrence
            result['passed'] = bool(recurrence['passed'] and min(result['ac_rms']) > 128
                                    and min(result['active_10ms_fraction']) >= .98
                                    and result['clipped_fraction'] < .0001
                                    and max(result['longest_near_zero_ms']) <= .5)
        if phase == 1:
            # Preserve the initial measurement: the NES core's analog filter
            # retains a decaying tail despite verified zero length status.
            # Keep the same strict silence threshold after 300 ms settling.
            settled_start = segment[0]['start_sample'] + rate*3//10
            settled = measure(pcm[settled_start:end], rate, None)
            result = dict(passed=settled['passed'], initial_measurement=result,
                          settled_measurement=settled, settled_start_sample=settled_start)
        phases.append(dict(phase=phase, start_sample=start, end_sample=end, **result))
    (out/'timeline.json').write_text(json.dumps(rows, indent=2)+'\n')
    report = dict(schema='rcr-nes-disabled-reload-v1', receipt=receipt, phases=phases,
                  passed=all(p['passed'] for p in phases), release_ready=False,
                  source_sha256=sha(source), config_sha256=sha(config),
                  wav_sha256=sha(out/'audio.wav'), timeline_sha256=sha(out/'timeline.json'),
                  scope='Executed ordered NES pulse disable/reload/re-enable; not hardware or full-game fidelity')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    if retrigger:
        report.update(profile='periodic-retrigger-control' if suppress_retriggers else 'periodic-retrigger',
                      pulse2=pulse2,
                      suppress_retriggers=suppress_retriggers,
                      scope='Executed NES periodic high-timer writes, tone and mute checks; waveform phase equivalence not yet scored')
        (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>NES ordered reload reference</title>'
        '<h1>Original NES ordered-write reference</h1><p>Asset-free NROM diagnostic: pulse, disable/reload/re-enable, valid reload, pitch change. '
        'Phase 1 has zero length status. The full waveform retains the filter tail; the report records both early and settled measurements.</p>'
        '<audio controls src="audio.wav"></audio><p><a href="report.json">Measurements and source hashes</a></p>')
    if retrigger:
        (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>NES retrigger reference</title>'
            '<h1>NES periodic pulse retrigger reference</h1><p>Duty and pitch held fixed between explicit '
            'mute/restart/pitch phases. Periodic high-timer writes every 32 frames. '
            f'Same-cycle suppression control: {suppress_retriggers}. Not a phase-fidelity score.</p>'
            '<audio controls src="audio.wav"></audio><p><a href="report.json">Measurements and hashes</a></p>')
    print(json.dumps({'passed':report['passed'],'phases':phases}, indent=2))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--retrigger', action='store_true')
    parser.add_argument('--pulse2', action='store_true')
    parser.add_argument('--suppress-retriggers', action='store_true')
    args = parser.parse_args()
    raise SystemExit(0 if check(args.core, args.out, args.retrigger, args.suppress_retriggers, args.pulse2) else 1)
