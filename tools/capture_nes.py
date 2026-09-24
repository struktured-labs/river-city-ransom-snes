"""Create a source-ROM-bound NES trace and screenshots in an isolated FCEUX run."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess

from PIL import Image

try:
    from .fceux_env import fceux_binary, require_palette
    from .rom import Rom
except ImportError:
    from fceux_env import fceux_binary, require_palette
    from rom import Rom

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=ROOT / "roms/river-city-ransom-us.nes")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=1800)
    parser.add_argument("--profile", choices=("title", "walk", "inventory"), default="title")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument('--replay', type=Path, help='Replay inputs from a verified original-NES benchmark capture')
    args = parser.parse_args()
    Rom.parse(args.rom.read_bytes()).require_rcr_us()
    if not 300 <= args.frames <= 18000:
        parser.error("frames must be 300..18000")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    replay_binding = None
    if args.replay:
        from benchmark_report import verify_capture
        receipt, rows = verify_capture(args.replay)
        if receipt['system'] != 'nes' or receipt['rom_sha256'] != sha(args.rom):
            raise ValueError('Replay must be bound to the same original NES ROM')
        (out/'replay-input.txt').write_text(''.join(str(sum(1 << button for button in row['input_requested']))+'\n' for row in rows))
        args.profile = 'replay'
        replay_binding = {'capture_sha256': sha(args.replay/'capture.json'),
                          'timeline_sha256': sha(args.replay/'timeline.json')}
    (ROOT / "build").mkdir(exist_ok=True)
    with (ROOT / "build/emulator.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        qt_platform = os.environ.get('RCR_QT_PLATFORM', 'xcb')
        if qt_platform not in ('xcb', 'offscreen'):
            raise ValueError('RCR_QT_PLATFORM must be xcb or offscreen')
        env = dict(os.environ, RCR_CAPTURE_DIR=str(out), RCR_CAPTURE_FRAMES=str(args.frames),
                   RCR_CAPTURE_PROFILE=args.profile, QT_QPA_PLATFORM=qt_platform)
        if args.replay:
            env['RCR_REPLAY_INPUT'] = str(out/'replay-input.txt')
        palette = require_palette()
        command = (["xvfb-run", "-a"] if qt_platform == 'xcb' else []) + [
                   str(fceux_binary()), "--no-config", "1", "--sound", "0",
                   "--palette", str(palette),
                   "--loadlua", str(ROOT / "tools/trace_nes.lua"), str(args.rom.resolve())]
        with (out / "emulator.log").open("w") as log:
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
        if status or not (out / "complete.json").exists():
            raise RuntimeError(f"FCEUX capture failed ({status}); see {out / 'emulator.log'}")
    for source in sorted(out.glob("frame-*.gd")):
        data = source.read_bytes()
        if len(data) != 11 + 256 * 240 * 4:
            raise ValueError(f"Unexpected GD screenshot size: {len(data)}")
        image = Image.frombytes("RGBA", (256, 240), data[11:], "raw", "ARGB").convert("RGB")
        image.save(source.with_suffix(".png"))
    manifest = {
        "schema": "rcr-nes-capture-v1", "rom_sha256": sha(args.rom),
        "script_sha256": sha(ROOT / "tools/trace_nes.lua"),
        "emulator_sha256": sha(fceux_binary()),
        "palette_sha256": sha(palette),
        "frames": args.frames, "profile": args.profile,
        "replay_binding": replay_binding,
        "files": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(out), "rom_sha256": manifest["rom_sha256"],
                      "screenshots": len(list(out.glob("*.png")))}, indent=2))


if __name__ == "__main__":
    main()
