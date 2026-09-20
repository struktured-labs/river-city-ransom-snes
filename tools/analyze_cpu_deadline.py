"""Compare paired host-only CPU event traces without assuming equal RNG state.

The observers execute no emulated reads or writes.  This report separates
mapper/pointer translation defects from different original-game stream choices,
which can legitimately occur in phase-driven replays with divergent scratch RNG.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


SCHEMA = {
    "nes": {
        "widths": (27, 41, 50), "frame": 0, "event": 3, "pc": 4,
        "a": 9, "state1a": 18, "stream_row": 24, "mode": 25,
        "stream_end": 26, "mapper": (27, 28, 29), "pointer": (30, 31),
        "entity": 46,
    },
    "snes": {
        "widths": (33, 47, 56), "frame": 0, "event": 3, "pc": 4,
        "a": 19, "state1a": 22, "stream_row": 28, "mode": 29,
        "stream_end": 30, "mapper": (33, 34, 35), "pointer": (36, 37),
        "entity": 52,
    },
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, system):
    spec = SCHEMA[system]
    with Path(path).open(newline="") as stream:
        rows = list(csv.reader(stream))
    if not rows:
        raise ValueError(f"{system} trace is empty")
    widths = Counter(map(len, rows))
    if len(widths) != 1 or next(iter(widths)) not in spec["widths"]:
        raise ValueError(f"{system} trace has unsupported/mixed widths: {dict(widths)}")
    try:
        for row in rows:
            int(row[spec["frame"]]); int(row[spec["event"]])
            int(row[spec["a"]]); int(row[spec["state1a"]])
    except (ValueError, IndexError) as exc:
        raise ValueError(f"{system} trace contains invalid numeric state") from exc
    return rows


def optional(row, indexes):
    if isinstance(indexes, int):
        indexes = (indexes,)
    if any(index >= len(row) for index in indexes):
        return None
    return tuple(int(row[index]) for index in indexes)


def commands(rows, system):
    spec = SCHEMA[system]
    result = []
    per_slot = Counter()
    for row in rows:
        if not row[spec["pc"]].lower().endswith("cf04"):
            continue
        slot = int(row[spec["state1a"]]) & 1
        result.append({
            "slot": slot,
            "ordinal": per_slot[slot],
            "frame": int(row[spec["frame"]]),
            "a": int(row[spec["a"]]),
            "producer_row": int(row[spec["stream_row"]]),
            "mode": int(row[spec["mode"]]),
            "stream_end": int(row[spec["stream_end"]]),
            "mapper": optional(row, spec["mapper"]),
            "pointer": optional(row, spec["pointer"]),
            "entity_selector": (optional(row, spec["entity"]) or (None,))[0],
        })
        per_slot[slot] += 1
    return result


def summarize(path, system, rows):
    spec = SCHEMA[system]
    events = Counter(int(row[spec["event"]]) for row in rows)
    cmd = commands(rows, system)
    frames = sorted({row["frame"] for row in cmd})
    return {
        "path": str(path), "sha256": sha(path), "rows": len(rows),
        "columns": len(rows[0]),
        "events": {str(key): events[key] for key in sorted(events)},
        "command_count": len(cmd),
        "commands_by_slot": {str(slot): sum(c["slot"] == slot for c in cmd)
                             for slot in (0, 1)},
        "command_frame_first": frames[0] if frames else None,
        "command_frame_last": frames[-1] if frames else None,
    }, cmd


def compare(nes, snes):
    paired = []
    for slot in (0, 1):
        left = [row for row in nes if row["slot"] == slot]
        right = [row for row in snes if row["slot"] == slot]
        paired.extend(zip(left, right))
    mapper_mismatches = []
    pointer_mismatches = []
    command_mismatches = []
    selector_mismatches = []
    for left, right in paired:
        where = {"slot": left["slot"], "ordinal": left["ordinal"],
                 "nes_row": left["producer_row"], "snes_row": right["producer_row"]}
        if left["mapper"] is not None and right["mapper"] is not None and left["mapper"] != right["mapper"]:
            mapper_mismatches.append({**where, "nes": left["mapper"], "snes": right["mapper"]})
        pointer_differs = (left["pointer"] is not None and right["pointer"] is not None and
                           left["pointer"] != right["pointer"])
        if pointer_differs:
            pointer_mismatches.append({**where, "nes": left["pointer"], "snes": right["pointer"]})
        if left["a"] != right["a"]:
            command_mismatches.append({**where, "nes": left["a"], "snes": right["a"]})
        if (pointer_differs and left["entity_selector"] is not None and right["entity_selector"] is not None and
                left["entity_selector"] != right["entity_selector"]):
            selector_mismatches.append({**where, "nes": left["entity_selector"],
                                        "snes": right["entity_selector"]})
    counts_equal = all(sum(c["slot"] == slot for c in nes) ==
                       sum(c["slot"] == slot for c in snes) for slot in (0, 1))
    classification = "matched"
    if mapper_mismatches:
        classification = "mapper-state-divergence"
    elif selector_mismatches and pointer_mismatches:
        classification = "different-original-game-stream-selection"
    elif pointer_mismatches:
        classification = "stream-pointer-divergence"
    elif command_mismatches or not counts_equal:
        classification = "producer-content-divergence"
    return {
        "classification": classification,
        "matched_commands": len(paired),
        "mapper_mismatch_count": len(mapper_mismatches),
        "pointer_mismatch_count": len(pointer_mismatches),
        "command_mismatch_count": len(command_mismatches),
        "selector_mismatch_count": len(selector_mismatches),
        "stream_lengths_equal": counts_equal,
        "first_mapper_mismatch": mapper_mismatches[0] if mapper_mismatches else None,
        "first_pointer_mismatch": pointer_mismatches[0] if pointer_mismatches else None,
        "first_command_mismatch": command_mismatches[0] if command_mismatches else None,
        "first_selector_mismatch": selector_mismatches[0] if selector_mismatches else None,
        "gates": {
            "mapper_state_matches_on_paired_commands": not mapper_mismatches,
            "producer_commands_match": not command_mismatches and counts_equal,
            "rng_independent_speed_comparison_ready": not selector_mismatches and counts_equal,
        },
    }


def analyze(nes_path, snes_path):
    nes_rows = load(nes_path, "nes")
    snes_rows = load(snes_path, "snes")
    nes_summary, nes_commands = summarize(nes_path, "nes", nes_rows)
    snes_summary, snes_commands = summarize(snes_path, "snes", snes_rows)
    if not nes_commands or not snes_commands:
        raise ValueError("both traces must contain at least one CF04 producer event")
    return {"schema": "rcr-paired-cpu-deadline-v1", "nes": nes_summary,
            "snes": snes_summary, "comparison": compare(nes_commands, snes_commands),
            "release_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nes", type=Path, required=True)
    parser.add_argument("--snes", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = analyze(args.nes, args.snes)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"out": str(args.out), "classification": report["comparison"]["classification"]}))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()
