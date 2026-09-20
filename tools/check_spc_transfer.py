"""Executed data-before-token regression, with delayed token-first negative control."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

try:
    from .analyze_spc_receive import audit
except ImportError:
    from analyze_spc_receive import audit

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(core, observer, out):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    reports = {}
    for name, negative in (('data-first', False), ('token-first', True)):
        env = dict(os.environ,
                   RCR_SPC_RECEIVE_TRACE=str(out / (name + '-receive.csv')),
                   RCR_AUDIO_BUS_TRACE=str(out / (name + '-bus.csv')))
        command = [sys.executable, str(ROOT / 'tools/check_audio.py'), '--core', str(observer),
                   '--out', str(out / name), '--transfer-delay']
        if negative:
            command.append('--token-first')
        run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
        (out / (name + '.log')).write_text(run.stdout + run.stderr)
        if (negative and (run.returncode == 0 or 'No sustained audio waveform' not in run.stderr)
                or not negative and run.returncode != 0):
            raise RuntimeError('Unexpected signal-test result: ' + name)
        report = audit(out / (name + '-bus.csv'), out / (name + '-receive.csv'),
                       out / (name + '-audit.json'))
        if report['passed'] == negative:
            raise RuntimeError('Receiver oracle did not distinguish token ordering')
        report['wav_sha256'] = sha(out / name / 'audio.wav')
        report['rom_sha256'] = sha(out / name / 'script.sfc')
        reports[name] = report
        shutil.copyfile(out / name / 'audio.wav', out / (name + '.wav'))
    if reports['data-first']['bytes_compared'] != reports['token-first']['bytes_compared']:
        raise RuntimeError('Positive and negative packet counts differ')
    # Independent uninstrumented run must preserve both timing and waveform.
    subprocess.run([sys.executable, str(ROOT / 'tools/check_audio.py'), '--core', str(core),
                    '--out', str(out / 'normal'), '--transfer-delay'],
                   stdout=subprocess.DEVNULL, check=True, timeout=60)
    for name in ('audio.wav', 'timeline.json'):
        if (out / 'normal' / name).read_bytes() != (out / 'data-first' / name).read_bytes():
            raise RuntimeError('Receiver observer changed ' + name)
    result = dict(schema='rcr-spc-transfer-regression-v1', passed=True, release_ready=False,
                  core_sha256=sha(core), observer_sha256=sha(observer),
                  source_sha256={str(p.relative_to(ROOT)): sha(p) for p in
                                 (ROOT/'snes/bringup.asm', ROOT/'snes/native_spc_frame.inc', ROOT/'tools/check_audio.py',
                                  ROOT/'tools/smoke_libretro.py', ROOT/'tools/snes9x_spc_receive.inc')},
                  variants=reports, observer_matches_normal=True,
                  scope='32 CPU NOPs before each data write; demonstrates protocol race resistance, not occurrence during normal gameplay or perceptual popping resolution')
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>SPC transfer-order regression</title>'
        '<h1>SPC receiver: data before token</h1>'
        '<p>Both variants pause the CPU before every data write. The old order lets the SPC consume stale data. '
        'This is a controlled stress test, not proof of the reported gameplay popping.</p>'
        f'<p>{reports["data-first"]["bytes_compared"]} bytes compared per variant. '
        f'Data-first mismatches: 0. Token-first mismatches: {reports["token-first"]["mismatch_count"]}.</p>'
        '<h2>Corrected order</h2><audio controls src="data-first.wav"></audio>'
        '<h2>Old order under delay</h2><audio controls src="token-first.wav"></audio>'
        '<p><a href="report.json">All mismatches, source hashes and measurements</a></p>')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'observer', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    r = check(a.core, a.observer, a.out)
    print(json.dumps(dict(passed=r['passed'], out=str(a.out))))
