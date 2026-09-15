"""Verify raw benchmark evidence and generate a fail-closed comparison dashboard."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import wave

import numpy as np
from PIL import Image, ImageDraw

try:
    from .benchmark_capture import SCENARIO, MAPPING, BUTTONS, RECTS, audio_stats, sha, matches
    from .audit import compare
except ImportError:
    from benchmark_capture import SCENARIO, MAPPING, BUTTONS, RECTS, audio_stats, sha, matches
    from audit import compare

POLICY = {"transition_tolerance_frames": 2, "transition_tolerance_fraction": 0.05,
          "active_ac_rms": 8.0, "reference_active_fraction": 0.95,
          "minimum_candidate_active_fraction": 0.90, "pause_tail_grace_frames": 60,
          "startup_partial_audio_frames": 1,
          "max_gameplay_silent_run_frames": 3}


def longest_run(values):
    longest = current = 0
    for value in values:
        current = current+1 if value else 0
        longest = max(longest, current)
    return longest


def phase_metrics(rows):
    active = [r["audio"]["ac_rms"] > POLICY["active_ac_rms"] for r in rows]
    return {"frames": len(rows), "active_audio_fraction": sum(active)/len(active) if active else 0,
            "longest_silent_run_frames": longest_run(not a for a in active),
            "mean_ac_rms": float(np.mean([r["audio"]["ac_rms"] for r in rows])) if rows else 0,
            "picture_changes": sum(a["video_sha256"] != b["video_sha256"] for a,b in zip(rows, rows[1:])),
            "probe_052b_changes": sum(a["probe_052b"] != b["probe_052b"] for a,b in zip(rows, rows[1:]))}


def pause_gate(reference_tail, candidate_tail, candidate_idle):
    # A dead sound engine must not receive a passing pause/silence verdict.
    if (not reference_tail["frames"] or reference_tail["active_audio_fraction"] != 0
            or not candidate_tail["frames"] or not candidate_idle
            or candidate_idle["active_audio_fraction"] < POLICY["minimum_candidate_active_fraction"]):
        return None
    return candidate_tail["active_audio_fraction"] == 0


def evaluate(reference, candidate):
    """Deterministic lower-level gates; these cannot certify perceptual fidelity."""
    gates = []
    for name in (p["name"] for p in SCENARIO if "until" in p):
        r, c = reference.get(name), candidate.get(name)
        allowed = max(POLICY["transition_tolerance_frames"],
                      (r or {}).get("frames", 0)*POLICY["transition_tolerance_fraction"])
        passed = bool(r and c and c["frames"] <= r["frames"]+allowed)
        gates.append({"gate": "transition:"+name, "passed": passed,
                      "reference_frames": r["frames"] if r else None,
                      "candidate_frames": c["frames"] if c else None})
    for name in ("idle", "walk", "attack", "resume_requested"):
        r, c = reference.get(name), candidate.get(name)
        applicable = bool(r and r["active_audio_fraction"] >= POLICY["reference_active_fraction"])
        passed = bool(applicable and c and c["active_audio_fraction"] >= POLICY["minimum_candidate_active_fraction"]
                      and c["longest_silent_run_frames"] <= POLICY["max_gameplay_silent_run_frames"])
        gates.append({"gate": "audio_presence:"+name, "passed": passed if applicable else None,
                      "reference": r, "candidate": c})
    return gates


def verify_capture(directory):
    try:
        from .benchmark_capture import scenario_for
    except ImportError:
        from benchmark_capture import scenario_for
    report = json.loads((directory / "capture.json").read_text())
    if report["schema"] != "rcr-benchmark-capture-v1" or report["release_ready"] is not False:
        raise ValueError("Invalid capture status")
    scenario = scenario_for(report.get('scenario_name', 'baseline'))
    if report["scenario"] != scenario or report["scenario_sha256"] != hashlib.sha256(json.dumps(scenario, sort_keys=True).encode()).hexdigest():
        raise ValueError("Scenario mismatch")
    system = report["system"]
    if system not in MAPPING or report["input_mapping"] != MAPPING[system]:
        raise ValueError("Wrong logical input mapping")
    for name, expected in (("timeline.json", report["timeline_sha256"]), ("audio.wav", report["audio_sha256"])):
        if sha(directory / name) != expected:
            raise ValueError(f"Evidence changed: {name}")
    if sha(directory / "nes.pal") != report["palette_sha256"]:
        raise ValueError("Palette changed")
    if set(report["templates"]) != set(RECTS):
        raise ValueError("Missing phase templates")
    for name, metadata in report["templates"].items():
        if name not in ("menu", "settings", "story", "street") or sha(directory / f"reference-{name}.png") != metadata["image"]:
            raise ValueError("Reference image changed")
    rows = json.loads((directory / "timeline.json").read_text())
    if not rows or len(rows) != report["frames"]:
        raise ValueError("Missing frame telemetry")
    with wave.open(str(directory / "audio.wav"), "rb") as source:
        if source.getnchannels() != 2 or source.getsampwidth() != 2 or source.getframerate() != round(report["sample_rate"]):
            raise ValueError("Wrong PCM geometry/rate")
        pcm = source.readframes(source.getnframes())
    next_frame, next_sample = 1, 0
    complete = True
    for index, segment in enumerate(report["segments"]):
        if index >= len(scenario):
            raise ValueError("Unexpected extra phase")
        phase = scenario[index]
        name = phase["name"]
        if (segment["name"] != name or segment["start_frame"] != next_frame
                or segment["frames"] != segment["end_frame"]-next_frame+1
                or not 0 < segment["frames"] <= phase["frames"]):
            raise ValueError("Phase coverage mismatch")
        if "until" not in phase and segment["frames"] != phase["frames"]:
            raise ValueError("Truncated measured phase")
        if "until" in phase and segment["transition_matched"] is not True:
            complete = False
            if index != len(report["segments"])-1:
                raise ValueError("Continued after an unrecognized phase")
        if segment["screenshot"] != name+".png" or sha(directory / (name+".png")) != segment["screenshot_sha256"]:
            raise ValueError("Screenshot changed or unsafe path")
        if 'ram_snapshot' in segment or 'ram_snapshot_sha256' in segment:
            if segment.get('ram_snapshot') != name+'.ram' or sha(directory / (name+'.ram')) != segment.get('ram_snapshot_sha256'):
                raise ValueError('RAM snapshot changed or unsafe path')
            snapshot = (directory / (name+'.ram')).read_bytes()
            if len(snapshot) < 2048 or hashlib.sha256(snapshot[:2048]).hexdigest() != rows[segment['end_frame']-1].get('ram_sha256'):
                raise ValueError('RAM snapshot and telemetry disagree')
        if 'vram_snapshot' in segment or 'vram_snapshot_sha256' in segment:
            if (segment.get('vram_snapshot') != name+'.vram'
                    or sha(directory/(name+'.vram')) != segment.get('vram_snapshot_sha256')
                    or (directory/(name+'.vram')).stat().st_size != 65536):
                raise ValueError('Video RAM snapshot changed or unsafe path')
        for offset, row in enumerate(rows[next_frame-1:segment["end_frame"]]):
            if row["frame"] != next_frame+offset or row["phase"] != name:
                raise ValueError("Non-contiguous telemetry")
            if report.get('scenario_name', '').startswith('traversal'):
                raw = bytes.fromhex(row.get('game_ram_hex', ''))
                if len(raw) != 2048 or hashlib.sha256(raw).hexdigest() != row['ram_sha256']:
                    raise ValueError('Traversal game RAM does not match frame telemetry')
            buttons = phase.get("buttons", [])
            if "pulse" in phase and offset % phase["pulse"][0] >= phase["pulse"][1]:
                buttons = []
            requested = sorted(MAPPING[system].get(b, BUTTONS[b]) for b in buttons)
            if row["input_requested"] != requested:
                raise ValueError("Input schedule changed")
            if row["audio_start_sample"] != next_sample:
                raise ValueError("Non-contiguous audio")
            count = row["audio"]["samples"]
            if count < 0 or (next_sample+count)*4 > len(pcm):
                raise ValueError("Truncated PCM")
            actual = audio_stats(pcm[next_sample*4:(next_sample+count)*4])
            if actual != row["audio"]:
                raise ValueError("Audio metrics do not match PCM")
            next_sample += count
        last = np.array(Image.open(directory / (name+".png")).convert("RGB"))
        if last.shape not in ((240,256,3), (239,256,3)):
            raise ValueError("Unexpected screenshot geometry")
        if hashlib.sha256(last.tobytes()).hexdigest() != rows[segment["end_frame"]-1]["video_sha256"]:
            raise ValueError("Screenshot and telemetry disagree")
        if "until" in phase and segment["transition_matched"] is True:
            template = np.array(Image.open(directory / ('reference-'+phase['until']+'.png')).convert('RGB'))
            if segment['frames'] < 3 or not matches(last, template, RECTS[phase['until']]):
                raise ValueError("Falsely recognized phase")
        next_frame = segment["end_frame"]+1
    if next_frame != len(rows)+1 or next_sample*4 != len(pcm):
        raise ValueError("Unaccounted video/audio evidence")
    complete = complete and len(report["segments"]) == len(scenario)
    if report["capture_complete"] != complete:
        raise ValueError("False completion claim")
    return report, rows


def plot(reference, candidate):
    """Per-phase AC RMS; separate normalized time axes prevent false alignment."""
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="650" viewBox="0 0 960 650">',
             '<rect width="960" height="650" fill="#121923"/>']
    for row, name in enumerate(("idle", "walk", "attack", "pause_requested", "resume_requested")):
        y = row*125+20
        parts.append(f'<text x="12" y="{y}" fill="white" font-size="15">{name}: per-frame AC RMS (shared amplitude scale)</text>')
        for source, color, offset in ((reference, "#58c8ff", 0), (candidate, "#ffb45e", 475)):
            values = [r["audio"]["ac_rms"] for r in source if r["phase"] == name]
            if values:
                points = " ".join(f'{15+offset+i*450/max(1,len(values)-1):.2f},{y+90-min(v/4096,1)*70:.2f}' for i,v in enumerate(values))
                parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{points}"/>')
            parts.append(f'<text x="{15+offset}" y="{y+108}" fill="{color}" font-size="12">{"NES reference" if offset == 0 else "SNES candidate"}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def build(reference_dir, candidate_dir, out):
    ref, rrows = verify_capture(reference_dir)
    cand, crows = verify_capture(candidate_dir)
    if ref.get('scenario_name', 'baseline') != 'baseline' or cand.get('scenario_name', 'baseline') != 'baseline':
        raise ValueError('Quality comparison requires baseline scenarios; transitions are diagnostic evidence only')
    if ref["system"] != "nes" or cand["system"] != "snes" or ref["templates"] != cand["templates"] or ref["palette_sha256"] != cand["palette_sha256"]:
        raise ValueError("Incompatible comparison inputs")
    if ref["rom_sha256"] != ref["templates"]["menu"]["source_rom"]:
        raise ValueError("Wrong reference ROM")
    # Phase-driven matching is disclosed, not passed off as frame synchronization.
    rmetrics = {s["name"]: phase_metrics(rrows[s["start_frame"]-1:s["end_frame"]]) for s in ref["segments"] if s["transition_matched"] is not False}
    cmetrics = {s["name"]: phase_metrics(crows[s["start_frame"]-1:s["end_frame"]]) for s in cand["segments"] if s["transition_matched"] is not False}
    gates = evaluate(rmetrics, cmetrics)
    gates.extend([
        {"gate": "all_phases_reached", "passed": ref["capture_complete"] and cand["capture_complete"]},
        {"gate": "input_delivery", "passed": all(r["input_requested"] == r["input_delivered"] for r in rrows+crows)},
        {"gate": "adapter_faults", "passed": not any(r["fault"] for r in crows)},
        {"gate": "same_video_rate", "passed": abs(ref["fps"]-cand["fps"]) < 0.1},
        {"gate": "continuous_audio_callbacks", "passed": all(abs(r["audio"]["samples"]-report["sample_rate"]/report["fps"]) <= 4 for report, rows in ((ref,rrows),(cand,crows)) for r in rows[POLICY["startup_partial_audio_frames"]:])},
    ])
    out.mkdir(parents=True, exist_ok=False)
    # Full frame diff is separate from the phase classifier's small glyph patch.
    settings = None
    if "settings" in cmetrics:
        settings, heat = compare(candidate_dir / "reference-settings.png", candidate_dir / "settings.png")
        heat.save(out / "settings-difference.png")
        gates.append({"gate": "settings_pixels", "passed": settings["mismatch_pixels"] == 0})
    tails = {}
    for name, rows in (("reference", rrows), ("candidate", crows)):
        paused = [r for r in rows if r["phase"] == "pause_requested"][POLICY["pause_tail_grace_frames"]:]
        tails[name] = phase_metrics(paused)
    gates.append({"gate": "pause_tail_noise", "passed": pause_gate(tails["reference"], tails["candidate"], cmetrics.get("idle"))})
    # Never equate presence/cadence with fidelity or an unvalidated game counter with speed.
    gates.extend([{"gate": "original_speed_full_gameplay", "passed": None},
                  {"gate": "music_and_sfx_fidelity", "passed": None},
                  {"gate": "physical_hardware_audio", "passed": None}])
    result = {"schema": "rcr-quality-benchmark-v1", "release_ready": False,
              "status": "failed" if any(g["passed"] is False for g in gates) else "incomplete",
              "policy": POLICY, "gates": gates, "reference": rmetrics, "candidate": cmetrics,
              "settings_pixels": settings, "pause_tail": tails,
              "candidate_rom_sha256": cand["rom_sha256"], "reference_rom_sha256": ref["rom_sha256"],
              "reference_capture_sha256": sha(reference_dir / "capture.json"),
              "candidate_capture_sha256": sha(candidate_dir / "capture.json"),
              "report_tool_sha256": sha(Path(__file__)),
              "notice": "Phase-driven equivalent actions, NOT cycle/frame-synchronized gameplay. Captured screenshots are real execution. Audio presence is not audio fidelity; requested pause is not proof that the game entered pause. Full-speed gameplay and physical audio remain unverified."}
    (out / "audio-timeline.svg").write_text(plot(rrows, crows))
    # Commercial audio remains in the ignored local audit directory, never copied to GitHub.
    for name, directory in (("nes", reference_dir), ("snes", candidate_dir)):
        shutil.copyfile(directory / "audio.wav", out / f"{name}-audio.wav")
    cases = [name for name in ("menu", "settings", "idle", "walk", "pause_requested") if name in rmetrics and name in cmetrics]
    collage = Image.new("RGB", (768, len(cases)*268), "#121923")
    draw = ImageDraw.Draw(collage)
    for row, name in enumerate(cases):
        y = row*268
        draw.text((8,y+7), f"{name} | NES / SNES / difference | phase-aligned, not frame-synchronized", fill="white")
        a, b = reference_dir/(name+".png"), candidate_dir/(name+".png")
        # Palette differences between emulator defaults are intentionally visible.
        _, difference = compare(a,b)
        for col, im in enumerate((Image.open(a), Image.open(b), difference)):
            collage.paste(im.crop((0,0,256,239)), (col*256,y+28))
    collage.save(out / "collage.png")
    result["files"] = {name: sha(out/name) for name in ("audio-timeline.svg", "collage.png", "nes-audio.wav", "snes-audio.wav")}
    evidence = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    result["evidence_sha256"] = evidence
    (out / "report.json").write_text(json.dumps(result, indent=2)+"\n")
    table = ''.join(f'<tr><td>{html.escape(g["gate"])}</td><td>{"PASS" if g["passed"] is True else "FAIL" if g["passed"] is False else "UNVERIFIED"}</td></tr>' for g in gates)
    audio_ui = ''
    for system, report, rows in (("nes", ref, rrows), ("snes", cand, crows)):
        buttons = ''.join(f'<button data-player="{system}" data-time="{rows[s["start_frame"]-1]["audio_start_sample"]/report["sample_rate"]:.6f}">{html.escape(s["name"])}</button>' for s in report["segments"])
        audio_ui += f'<h2>{system.upper()} recorded audio</h2><audio id="{system}" controls preload="metadata" src="{system}-audio.wav"></audio><p>{buttons}</p>'
    document = f'''<!doctype html><meta charset="utf-8"><title>RCR quality gate — {result["status"]}</title>
<style>body{{background:#121923;color:#eee;font:16px system-ui;max-width:1000px;margin:2em auto;padding:1em}}td{{padding:.3em 1em;border-bottom:1px solid #456}}img{{max-width:100%}}button{{margin:3px}}textarea{{width:100%;min-height:6em}}</style>
<h1>Quality gate: {result["status"].upper()} — not release-ready</h1><p>{html.escape(result["notice"])}</p>
<p>Audio playback requires the local audit bundle. ROMs and recorded game audio are deliberately omitted from the GitHub summary.</p>
<p>Candidate: {cand["rom_sha256"]}</p><table>{table}</table>
<h2>Audio availability</h2><img src="audio-timeline.svg" alt="Per-phase original and candidate audio amplitude">{audio_ui}
<h2>Real execution comparisons</h2><img src="collage.png" alt="NES, SNES and difference collage">
<h2>Human audio/gameplay review</h2><p>No automatic pass replaces listening. Notes apply only to evidence {evidence}.</p>
<textarea id="notes" placeholder="Record phase, timestamp, missing channels, sputtering, or speed mismatch"></textarea><button id="export">Export review</button>
<script>const identity={json.dumps(evidence)};const box=document.getElementById('notes');box.value=localStorage.getItem(identity)||'';
box.oninput=()=>localStorage.setItem(identity,box.value);document.querySelectorAll('[data-player]').forEach(b=>b.onclick=()=>{{document.querySelectorAll('audio').forEach(a=>a.pause());const a=document.getElementById(b.dataset.player);a.currentTime=Number(b.dataset.time);a.play();}});
document.getElementById('export').onclick=()=>{{const blob=new Blob([JSON.stringify({{schema:'rcr-quality-review-v1',evidence_sha256:identity,notes:box.value,release_approval:false}},null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='review-'+identity+'.json';a.click();URL.revokeObjectURL(a.href);}};</script>'''
    (out / "index.html").write_text(document)
    bundle = {"schema": "rcr-quality-bundle-v1", "files": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    (out / "bundle.json").write_text(json.dumps(bundle, indent=2)+"\n")
    print(json.dumps({"out": str(out), "status": result["status"], "failed": [g["gate"] for g in gates if g["passed"] is False]}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "candidate", "out"):
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    result = build(args.reference, args.candidate, args.out)
    raise SystemExit(1 if result["status"] != "passed" else 0)
