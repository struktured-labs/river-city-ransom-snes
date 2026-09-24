"""Input-only FCEUX dump of Novice vs Advanced enemy stats."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess

from PIL import Image

from .fceux_env import fceux_binary, require_palette
from .nes_difficulty import prg_from, simon_spawn, skill_add_table
from .rom import Rom

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, default=ROOT / 'roms/river-city-ransom-us.nes')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    Rom.parse(args.rom.read_bytes()).require_rcr_us()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    prg = prg_from(args.rom.read_bytes())
    (out / 'simon-table.json').write_text(json.dumps({
        'skill_add': list(skill_add_table(prg)),
        'novice': simon_spawn(prg, 1)[0],
        'advanced': simon_spawn(prg, 2)[0],
        'base': simon_spawn(prg, 1)[1],
    }, indent=2) + '\n')
    (ROOT / 'build').mkdir(exist_ok=True)
    with (ROOT / 'build/emulator.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        env = dict(os.environ, RCR_CAPTURE_DIR=str(out), QT_QPA_PLATFORM='xcb')
        command = ['xvfb-run', '-a', str(fceux_binary()), '--no-config', '1', '--sound', '0',
                   '--palette', str(require_palette()),
                   '--loadlua', str(ROOT / 'tools/dump_nes_difficulty.lua'),
                   str(args.rom.resolve())]
        with (out / 'emulator.log').open('w') as log:
            process = subprocess.Popen(command, cwd=out, env=env, stdout=log, stderr=log,
                                       start_new_session=True)
            try:
                status = process.wait(timeout=args.timeout)
            except BaseException:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise
        if status or not (out / 'complete.json').exists():
            raise RuntimeError(f'FCEUX dump failed ({status}); see {out / "emulator.log"}')
    for source in sorted(out.glob('*.gd')):
        data = source.read_bytes()
        Image.frombytes('RGBA', (256, 240), data[11:], 'raw', 'ARGB').convert('RGB').save(
            source.with_suffix('.png'))
    print(json.dumps({
        'out': str(out),
        'complete': json.loads((out / 'complete.json').read_text()),
        'events': [json.loads(line) for line in (out / 'dump.jsonl').read_text().splitlines()],
    }, indent=2))


if __name__ == '__main__':
    main()
