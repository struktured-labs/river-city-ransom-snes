"""Build the pinned NES reference core; no commercial ROMs are downloaded."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REVISION = "236ccdfc911e84c60fea6b9d0699c2d440a8de14"


def main():
    target = ROOT / ".deps/fceumm"
    if not target.exists():
        target.mkdir(parents=True)
        subprocess.run(["git", "init", str(target)], check=True)
        subprocess.run(["git", "-C", str(target), "fetch", "--depth=1",
                        "https://github.com/libretro/libretro-fceumm.git", REVISION], check=True)
        subprocess.run(["git", "-C", str(target), "checkout", "--detach", REVISION], check=True)
    actual = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(target), "diff", "HEAD"], text=True)
    if actual != REVISION or dirty:
        raise SystemExit("Unexpected reference-core revision/modifications; left intact")
    subprocess.run(["make", "-C", str(target), "-f", "Makefile.libretro", "-j4"], check=True)
    print(target / "fceumm_libretro.so")


if __name__ == "__main__":
    main()
