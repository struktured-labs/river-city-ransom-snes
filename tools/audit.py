"""Build a hash-bound, reviewable renderer audit. Generated media stays local."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(reference, actual):
    a = np.asarray(Image.open(reference).convert("RGB"))
    b = np.asarray(Image.open(actual).convert("RGB"))
    if a.shape != (240, 256, 3) or b.shape != (239, 256, 3):
        raise ValueError(f"Unexpected frame geometry {a.shape} / {b.shape}")
    # Explicit hardware viewport, never search for a favourable alignment.
    a = a[:239]
    mismatch = np.any((a >> 3) != (b >> 3), axis=2)
    heat = np.zeros_like(a)
    heat[mismatch] = (255, 64, 100)
    return {"pixels_compared": 239 * 256, "mismatch_pixels": int(mismatch.sum()),
            "rgb_max_error": int(np.max(np.abs(a.astype(int) - b.astype(int)))),
            "passed": not bool(mismatch.any()), "comparison": "top 239 rows, RGB reduced to 5 bits/channel"}, Image.fromarray(heat)


def build(capture, core, out, frames):
    manifest = json.loads((capture / "manifest.json").read_text())
    if manifest["schema"] != "rcr-nes-capture-v1":
        raise ValueError("Unsupported source capture schema")
    out.mkdir(parents=True, exist_ok=False)
    media = out / "media"
    media.mkdir()
    cases = []
    for frame in frames:
        fixture = out / f"fixture-{frame:05d}"
        subprocess.run([sys.executable, str(ROOT / "tools/render_fixture.py"), "--capture", str(capture),
                        "--frame", str(frame), "--out", str(fixture)], check=True)
        source = capture / f"frame-{frame:05d}.png"
        ref = media / f"nes-{frame:05d}.png"
        actual = media / f"snes-{frame:05d}.png"
        if sha(source) != manifest["files"][source.name]:
            raise ValueError("Reference screenshot changed")
        shutil.copyfile(source, ref)
        run = subprocess.run([sys.executable, str(ROOT / "tools/smoke_libretro.py"), "--core", str(core),
                              "--rom", str(fixture / "render.sfc"), "--kind", "render",
                              "--receipt", str(fixture / "receipt.json"),
                              "--screenshot", str(actual)], check=True, capture_output=True, text=True)
        (fixture / "emulator-result.txt").write_text(run.stdout + run.stderr)
        receipt = json.loads((fixture / "receipt.json").read_text())
        if (receipt["rom_sha256"] != sha(fixture / "render.sfc") or receipt["core_sha256"] != sha(core)
                or receipt["screenshot_sha256"] != sha(actual) or receipt["status"] != "passed"):
            raise ValueError("Emulator receipt does not authenticate the candidate evidence")
        metrics, heat = compare(ref, actual)
        difference = media / f"difference-{frame:05d}.png"
        heat.save(difference)
        identity = {"rom_sha256": sha(fixture / "render.sfc"), "reference_sha256": sha(ref),
                    "actual_sha256": sha(actual), "difference_sha256": sha(difference),
                    "core_sha256": sha(core), "metrics": metrics,
                    "receipt_sha256": sha(fixture / "receipt.json"),
                    "audit_tool_sha256": sha(Path(__file__)),
                    "fixture_manifest_sha256": sha(fixture / "manifest.json")}
        cases.append({"id": f"renderer-frame-{frame}", "frame": frame,
                      "title": f"Original frame {frame} → native SNES renderer fixture",
                      "reference": f"media/{ref.name}", "actual": f"media/{actual.name}",
                      "difference": f"media/{difference.name}", **identity,
                      "evidence_sha256": hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()})
    document = {"schema": "rcr-visual-audit-v1", "kind": "renderer fixtures, not gameplay validation",
                "source_rom_sha256": manifest["rom_sha256"], "capture_manifest_sha256": sha(capture / "manifest.json"),
                "cases": cases, "passed": all(c["metrics"]["passed"] for c in cases)}
    (out / "audit.json").write_text(json.dumps(document, indent=2) + "\n")
    # Only this directory is publishable; it contains no game/snapshot binaries.
    site = out / "site"
    site.mkdir()
    shutil.copytree(media, site / "media")
    shutil.copyfile(out / "audit.json", site / "audit.json")
    (site / "index.html").write_text(page(document))
    collage = Image.new("RGB", (256 * 3, (240 + 28) * len(cases)), "#131b26")
    draw = ImageDraw.Draw(collage)
    for row, case in enumerate(cases):
        y = row * 268
        draw.text((8, y + 7), f"Frame {case['frame']} | NES / SNES / difference | {case['metrics']['mismatch_pixels']} mismatched pixels", fill="white")
        for col, key in enumerate(("reference", "actual", "difference")):
            collage.paste(Image.open(site / case[key]), (col * 256, y + 28))
    collage.save(site / "collage.png")
    document["collage_sha256"] = sha(site / "collage.png")
    (out / "audit.json").write_text(json.dumps(document, indent=2) + "\n")
    (site / "audit.json").write_text(json.dumps(document, indent=2) + "\n")
    print(json.dumps({"site": str(site), "cases": len(cases), "passed": document["passed"]}, indent=2))
    return document


def page(document):
    cards = []
    for c in document["cases"]:
        status = "pass" if c["metrics"]["passed"] else "fail"
        pictures = "".join(f'<figure><img loading="lazy" src="{c[key]}" alt="{label} frame {c["frame"]}"><figcaption>{label}</figcaption></figure>'
                           for key, label in (("reference", "NES reference"), ("actual", "SNES hardware output"), ("difference", "5-bit colour difference")))
        cards.append(f'<article data-evidence="{c["evidence_sha256"]}" data-case="{c["id"]}"><h2>{html.escape(c["title"])}</h2>'
                     f'<p class="{status}">{c["metrics"]["mismatch_pixels"]:,} mismatched pixels / {c["metrics"]["pixels_compared"]:,}</p>'
                     f'<div class="images">{pictures}</div><details><summary>Exact evidence identity</summary><pre>{html.escape(json.dumps({k:c[k] for k in ("rom_sha256", "reference_sha256", "actual_sha256", "core_sha256", "evidence_sha256")}, indent=2))}</pre></details>'
                     '<label>My review <select><option value="unreviewed">Unreviewed</option><option value="good">Looks right</option><option value="issue">Issue</option><option value="recapture">Recapture</option></select></label>'
                     '<textarea placeholder="Your notes for this exact evidence set" aria-label="Review notes"></textarea></article>')
    result = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>River City Ransom · Port audit</title><style>
*{box-sizing:border-box}body{margin:0;background:#0b111b;color:#e6edf7;font:16px/1.5 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:32px 20px}h1{font-size:36px;line-height:1.1}h2{font-size:20px}p{max-width:900px}.notice{background:#283022;border:1px solid #6c804a;padding:18px;border-radius:8px}article{background:#131d2b;padding:20px;margin:24px 0;border:1px solid #2c3d55;border-radius:10px}.images{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}figure{margin:0}img{display:block;width:100%;image-rendering:pixelated;background:black}figcaption{font-size:13px;color:#b4c2d7;margin-top:8px}.pass{color:#8fe2ad}.fail{color:#ff9aab}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}select,textarea,button{background:#0b111b;color:#e6edf7;border:1px solid #586d8a;border-radius:4px;padding:8px;font:inherit}textarea{display:block;width:100%;min-height:70px;margin-top:12px}button{cursor:pointer}a{color:#94c7ff}header small{color:#9dafc5}.toolbar{position:sticky;top:0;background:#0b111bec;padding:12px 0;z-index:2}@media(max-width:650px){main{padding:20px 10px}.images{grid-template-columns:1fr}figure{max-width:512px}h1{font-size:28px}}
</style><main><header><small>STRUKTURED LABS / DEVELOPMENT EVIDENCE</small><h1>River City Ransom<br>NES → SNES port audit</h1></header>
<p class="notice">This audit covers native SNES renderer fixtures built from measured NES PPU states. It does <strong>not</strong> establish playable gameplay or full-game compatibility. The CPU integration prototype is a separate work in progress.</p>
<p>Original graphics, no replacement artwork. Comparisons use the top 239 NES rows to match SNES overscan output, with both sides reduced to 5-bit colour precision. The NES's final row is outside this hardware comparison. No alignment search or image rescaling is used for the scores.</p>
<div class="toolbar"><button id="export">Export my reviews</button> <a href="collage.png">Open full collage</a> · <a href="audit.json">Machine evidence</a></div>
<p>Reviews save in this browser, keyed to each exact candidate and evidence hash. Export to share them; new evidence starts unreviewed.</p>
''' + "\n".join(cards) + '''<script>
const articles=[...document.querySelectorAll('article')];
for(const a of articles){const key='rcr-review-v1:'+a.dataset.evidence;const s=a.querySelector('select'),t=a.querySelector('textarea');try{const v=JSON.parse(localStorage.getItem(key)||'null');if(v){s.value=v.verdict;t.value=v.notes}}catch{}const save=()=>localStorage.setItem(key,JSON.stringify({verdict:s.value,notes:t.value,updated_at:new Date().toISOString()}));s.addEventListener('change',save);t.addEventListener('input',save)}
document.querySelector('#export').onclick=()=>{const reviews=articles.map(a=>({case_id:a.dataset.case,evidence_sha256:a.dataset.evidence,verdict:a.querySelector('select').value,notes:a.querySelector('textarea').value}));const blob=new Blob([JSON.stringify({schema:'rcr-human-review-v1',exported_at:new Date().toISOString(),reviews},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='rcr-audit-reviews.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
</script></main></html>'''
    if document.get("notice"):
        start = result.index('<p class="notice">')
        end = result.index('</p>', start) + 4
        result = result[:start] + '<p class="notice">' + html.escape(document["notice"]) + '</p>' + result[end:]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--frames", type=int, nargs="+", default=[120, 300, 600])
    args = parser.parse_args()
    build(args.capture, args.core, args.out, args.frames)
