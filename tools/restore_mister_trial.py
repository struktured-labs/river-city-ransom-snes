"""Reload a prior hash-bound cartridge without replacing files or saved settings."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex

from tools.benchmark_report import sha
from tools.capture_mister_boot import remote


def restore(boot, out):
    if out.exists():
        raise ValueError('Need fresh restoration receipt')
    prior = json.loads(boot.read_text())
    digest = prior['rom_sha256']
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Invalid cartridge hash')
    rom = '/media/fat/games/SNES/RCR-SNES-' + digest[:12] + '.sfc'
    launcher = '/media/fat/RCR-SNES-' + digest[:12] + '.mgl'
    if (prior['rom'], prior['launcher']) != (rom, launcher):
        raise ValueError('Unexpected prior paths')
    for path, expected in ((rom, digest), (launcher, prior['launcher_sha256']),
                           ('/media/fat/config/SNES.CFG', prior['config_before'])):
        if remote('sha256sum ' + shlex.quote(path)).split()[0] != expected:
            raise ValueError('Prior file differs: ' + path)
    report = dict(requested_utc=datetime.now(timezone.utc).isoformat(),
        process_before=remote('ps -ef | grep "[M]iSTer /media/fat/_Console/"'),
        rom=rom, rom_sha256=digest, launcher=launcher,
        saved_config_sha256=prior['config_before'],
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/capture_mister_boot.py'), boot)},
        scope='Reload request for hash-verified existing cartridge. Restarts, not a save-state '
              'restore; controller state and visible result require separate handoff checks.')
    remote("printf '%s\\n' " + shlex.quote('load_core ' + launcher) + ' > /dev/MiSTer_cmd')
    report['returned_utc'] = datetime.now(timezone.utc).isoformat()
    with out.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('boot', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    restore(**vars(parser.parse_args()))
