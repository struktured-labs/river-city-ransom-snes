"""Build an optional pinned Snes9x core with reproducible debug observability."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REVISION = "7a8878f1306f65594c30b7d86dee41d972c2e495"


def main():
    target = ROOT / ".deps/snes9x"
    patch = ROOT / "tools/snes9x-debug.patch"
    if not target.exists():
        target.mkdir(parents=True)
        subprocess.run(["git", "init", str(target)], check=True)
        subprocess.run(["git", "-C", str(target), "fetch", "--depth=1",
                        "https://github.com/snes9xgit/snes9x.git", REVISION], check=True)
        subprocess.run(["git", "-C", str(target), "checkout", "--detach", REVISION], check=True)
    actual = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
    if actual != REVISION:
        raise SystemExit("Unexpected emulator revision; existing checkout left intact")
    diff = subprocess.check_output(["git", "-C", str(target), "diff", "HEAD"], text=True)
    if not diff:
        subprocess.run(["git", "-C", str(target), "apply", "--check", str(patch)], check=True)
        subprocess.run(["git", "-C", str(target), "apply", str(patch)], check=True)
    elif diff != patch.read_text():
        raise SystemExit("Unexpected emulator modifications; existing checkout left intact")
    subprocess.run(["make", "-C", str(target / "libretro"), "-j4"], check=True)
    print(target / "libretro/snes9x_libretro.so")


if __name__ == "__main__":
    main()
