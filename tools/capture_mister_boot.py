"""Load a hash-named test cartridge only after the bounded raw recorder is ready.

This is a hardware trial, not a release gate. Saved settings and the previous
cartridge are preserved. No controller input or OBS routing changes are made.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import selectors
import shlex
import subprocess

from tools.benchmark_report import sha


def stamp():
    return datetime.now(timezone.utc).isoformat()


def remote(command):
    return subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o',
        'ConnectTimeout=8', 'rivalmage', command], text=True, timeout=15)


def capture(candidate, out, remote_out):
    if out.exists() or remote_out.exists():
        raise ValueError('Need fresh evidence paths')
    rom = candidate / 'native-cpu.sfc'
    digest = sha(rom)
    target = '/media/fat/games/SNES/RCR-SNES-' + digest[:12] + '.sfc'
    launcher = '/media/fat/RCR-SNES-' + digest[:12] + '.mgl'
    # Fixed host/core, safe generated names, and no overwrite of any cartridge.
    remote('test -p /dev/MiSTer_cmd && test ! -e ' + shlex.quote(target) +
           ' && test ! -e ' + shlex.quote(launcher))
    config_before = remote('sha256sum /media/fat/config/SNES.CFG').split()[0]
    before = remote('ps -ef | grep "[M]iSTer /media/fat/_Console/"')
    out.mkdir(parents=True, exist_ok=False)
    mgl = out / 'launcher.mgl'
    mgl.write_text('<mistergamedescription>\n  <rbf>_Console/SNES_20260603</rbf>\n'
        '  <file delay="2" type="f" index="0" path="' + target + '"/>\n'
        '</mistergamedescription>\n')
    for source, destination in ((rom, target), (mgl, launcher)):
        subprocess.run(['scp', '-O', str(source), 'rivalmage:' + destination],
                       check=True, timeout=20)
        if remote('sha256sum ' + shlex.quote(destination)).split()[0] != sha(source):
            raise ValueError('Remote cartridge/launcher differs')
    helper = Path('tools/capture_blackmagic_raw.py')
    remote_helper = '/tmp/rcr-raw-boot-' + sha(helper)[:16] + '.py'
    subprocess.run(['scp', '-O', str(helper), 'blackmage:' + remote_helper], check=True, timeout=15)
    command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'blackmage',
               '/home/struktured/.local/bin/python3', remote_helper,
               '--seconds', '30', '--out', str(remote_out)]
    result = dict(started_utc=stamp(), rom=target, rom_sha256=digest,
        launcher=launcher, launcher_sha256=sha(mgl), process_before=before,
        config_before=config_before, remote_out=str(remote_out),
        sources={str(p): sha(p) for p in (Path(__file__), rom, mgl, helper)},
        release_ready=False, physical_audio_verified=False,
        scope='Hash-verified unique cartridge and launcher, launch after raw-recorder handshake. '
              'Process identity is not cartridge RAM readback. No controller input; no speed '
              'or acoustic-quality certification. Previous cartridge and saved settings preserved.')
    with (out / 'recorder.stderr').open('x') as error_log:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_log, text=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                if not selector.select(timeout=12):
                    raise RuntimeError('Recorder ready handshake timed out')
                ready = json.loads(process.stdout.readline())
            if not ready.get('recording_ready') or ready.get('out') != str(remote_out):
                raise ValueError('Wrong recorder handshake')
            result['ready'] = ready
            result['launch_requested_utc'] = stamp()
            remote("printf '%s\\n' " + shlex.quote('load_core ' + launcher) + ' > /dev/MiSTer_cmd')
            result['launch_returned_utc'] = stamp()
            result['recorder_stdout'] = process.communicate(timeout=40)[0]
            if process.returncode:
                raise RuntimeError('Recorder failed')
            result['process_after'] = remote('ps -ef | grep "[M]iSTer /media/fat/_Console/"')
            if launcher not in result['process_after']:
                raise ValueError('Expected launcher not running')
            result['config_after'] = remote('sha256sum /media/fat/config/SNES.CFG').split()[0]
            if result['config_after'] != config_before:
                raise ValueError('Saved config changed')
            result['recording_report_sha256'] = sha(remote_out / 'report.json')
        except Exception as exc:
            result['error'] = str(exc)
            # Let the remote owner stop OBS and remove its raw tap.
            try:
                result['recorder_stdout'] = process.communicate(timeout=45)[0]
            except subprocess.TimeoutExpired:
                result['recorder_cleanup_unverified'] = True
            raise
        finally:
            result['finished_utc'] = stamp()
            (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(rom_sha256=digest, launcher=launcher, saved_config_unchanged=True,
                         recording=str(remote_out), out=str(out))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'out', 'remote-out'):
        parser.add_argument('--' + name, type=Path, required=True)
    capture(**vars(parser.parse_args()))
