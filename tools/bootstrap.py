"""Fetch pinned development dependencies into the ignored .deps directory."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    dependencies = json.loads((ROOT / "tools/dependencies.json").read_text())
    for name, spec in dependencies.items():
        target = ROOT / ".deps" / name
        if not target.exists():
            target.mkdir(parents=True)
            subprocess.run(["git", "init", str(target)], check=True)
            subprocess.run(["git", "-C", str(target), "fetch", "--depth=1",
                            spec["url"], spec["commit"]], check=True)
            subprocess.run(["git", "-C", str(target), "checkout", "--detach",
                            spec["commit"]], check=True)
        actual = subprocess.check_output(
            ["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
        if actual != spec["commit"]:
            raise SystemExit(f"Wrong revision in {target}: {actual}")
        if subprocess.check_output(["git", "-C", str(target), "status",
                                    "--porcelain", "--untracked-files=no"]):
            raise SystemExit(f"Tracked dependency files modified in {target}")
    audio = dependencies["upernes"]
    data = (ROOT / ".deps/upernes" / audio["audio_path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != audio["audio_sha256"]:
        raise SystemExit("Unexpected audio engine checksum")
    subprocess.run(["make", "-C", str(ROOT / ".deps/cc65"), "-j4", "ca65", "ld65"],
                   check=True)


if __name__ == "__main__":
    main()
