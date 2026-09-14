"""Capture actual native execution, keeping phase/timing gaps visible to reviewers."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw
try:
    from .audit import sha, compare, page
except ImportError:
    from audit import sha, compare, page

ROOT = Path(__file__).resolve().parents[1]


def build(candidate, title, walk, core, out):
    manifest = json.loads((candidate / "manifest.json").read_text())
    rom = candidate / "native-cpu.sfc"
    if sha(rom) != manifest["rom_sha256"]:
        raise ValueError("Candidate changed since build")
    out.mkdir(parents=True, exist_ok=False)
    site = out / "site"
    media = site / "media"
    media.mkdir(parents=True)
    cases = []
    for name, capture, reference_frame, native_frames, profile in (
            ("menu", title, 600, 1800, "title"),
            ("street", walk, 1800, 3600, "walk")):
        capture_manifest = json.loads((capture / "manifest.json").read_text())
        source = capture / f"frame-{reference_frame:05d}.png"
        if (sha(source) != capture_manifest["files"][source.name]
                or capture_manifest["rom_sha256"] != manifest["source_rom_sha256"]):
            raise ValueError("Reference image identity mismatch")
        ref = media / f"{name}-nes.png"
        actual = media / f"{name}-snes.png"
        difference = media / f"{name}-difference.png"
        receipt_path = site / f"{name}-receipt.json"
        shutil.copyfile(source, ref)
        subprocess.run([sys.executable, str(ROOT / "tools/smoke_libretro.py"),
                        "--core", str(core), "--rom", str(rom), "--kind", "native", "--profile", profile,
                        "--frames", str(native_frames), "--screenshot", str(actual),
                        "--receipt", str(receipt_path)], check=True)
        receipt = json.loads(receipt_path.read_text())
        if (receipt["rom_sha256"] != sha(rom) or receipt["screenshot_sha256"] != sha(actual)
                or receipt["core_sha256"] != sha(core) or receipt["status"] != "passed"):
            raise ValueError("Live emulator evidence does not match candidate")
        metrics, heat = compare(ref, actual)
        heat.save(difference)
        identity = {"rom_sha256": sha(rom), "reference_sha256": sha(ref), "actual_sha256": sha(actual),
                    "difference_sha256": sha(difference), "core_sha256": sha(core), "metrics": metrics,
                    "candidate_manifest_sha256": sha(candidate / "manifest.json"),
                    "capture_manifest_sha256": sha(capture / "manifest.json"),
                    "receipt_sha256": sha(receipt_path), "audit_tool_sha256": sha(Path(__file__)),
                    "reference_frame": reference_frame, "native_frames": native_frames,
                    "input_profile": profile, "synchronized": False}
        cases.append({"id": name, "frame": reference_frame,
                      "title": f"Live {name}: NES frame {reference_frame} / SNES frame {native_frames} (not synchronized)",
                      "reference": f"media/{ref.name}", "actual": f"media/{actual.name}",
                      "difference": f"media/{difference.name}", **identity,
                      "evidence_sha256": hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()})
    document = {"schema": "rcr-visual-audit-v1", "kind": "live native execution; NOT synchronized gameplay validation",
                "notice": "These screenshots come from original game code executing on the SNES CPU. They are NOT static renderer fixtures. CPU progress and adapter faults are checked, but reference and candidate timing/input schedules are not synchronized. Pixel scores expose differences; they do not establish gameplay fidelity. Scrolling, raster IRQs, speed, and audio accuracy remain incomplete.",
                "cases": cases, "passed": False, "release_ready": False,
                "limitations": manifest["limitations"]}
    (site / "audit.json").write_text(json.dumps(document, indent=2) + "\n")
    (site / "index.html").write_text(page(document))
    collage = Image.new("RGB", (768, 268 * len(cases)), "#131b26")
    draw = ImageDraw.Draw(collage)
    for row, case in enumerate(cases):
        y = row * 268
        draw.text((8, y + 7), f"LIVE {case['id']} | NES / SNES / difference | NOT frame-synchronized", fill="white")
        for col, key in enumerate(("reference", "actual", "difference")):
            collage.paste(Image.open(site / case[key]), (col * 256, y + 28))
    collage.save(site / "collage.png")
    print(site)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "title", "walk", "core", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    build(args.candidate, args.title, args.walk, args.core, args.out)
