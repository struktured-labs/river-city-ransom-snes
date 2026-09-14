"""Fail closed on changed images, scores, identity or unsafe gallery payloads."""
import argparse
import hashlib
import json
from pathlib import Path

try:
    from .audit import compare, sha, page
except ImportError:
    from audit import compare, sha, page


def verify(site):
    site = site.resolve()
    for path in site.rglob("*"):
        if path.is_symlink() or (path.is_file() and path.suffix not in (".png", ".json", ".html")):
            raise ValueError(f"Unsafe publication payload: {path.name}")
    document = json.loads((site / "audit.json").read_text())
    if document["schema"] != "rcr-visual-audit-v1" or not document["cases"]:
        raise ValueError("Missing or unsupported audit cases")
    if sha(site / "collage.png") != document["collage_sha256"]:
        raise ValueError("Collage changed")
    if (site / "index.html").read_text() != page(document):
        raise ValueError("Gallery HTML differs from authenticated case rendering")
    for case in document["cases"]:
        paths = {}
        for key in ("reference", "actual", "difference"):
            path = (site / case[key]).resolve()
            if not path.is_relative_to(site) or not path.is_file():
                raise ValueError("Evidence path leaves the gallery or is missing")
            if sha(path) != case[key + "_sha256"]:
                raise ValueError("Evidence image changed")
            paths[key] = path
        metrics, heat = compare(paths["reference"], paths["actual"])
        if metrics != case["metrics"]:
            raise ValueError("Reported pixel scores do not match images")
        from PIL import Image
        if heat.tobytes() != Image.open(paths["difference"]).convert("RGB").tobytes():
            raise ValueError("Difference image is not the measured difference")
        identity = {k: v for k, v in case.items() if k not in
                    ("id", "frame", "title", "reference", "actual", "difference", "evidence_sha256")}
        if hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest() != case["evidence_sha256"]:
            raise ValueError("Evidence identity changed")
    if document["passed"] and (any(not c["metrics"]["passed"] for c in document["cases"])
                               or any(c.get("synchronized") is False for c in document["cases"])):
        raise ValueError("Audit claims a pass unsupported by its evidence")
    return {"cases": len(document["cases"]), "integrity": "passed", "visual_pass": document["passed"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    print(json.dumps(verify(parser.parse_args().site), indent=2))
