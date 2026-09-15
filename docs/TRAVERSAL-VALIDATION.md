# Matched walking diagnostic

The `traversal` capture scenario recognizes the original menu/settings/story/
street sequence before holding Right for 4,320 display frames. It retains a
screenshot every 120 walking frames and all 2 KiB of original-game RAM every
frame, bound to the existing RAM and timeline hashes. No RAM writes, emulator
speed overrides, save-state injection, or enemy removal are used.

First capture: `build/traversal-01/{nes,snes}`, using the original NES ROM and
native candidate `8e58e706bab2cd0d29cdc264df83d711e862e78cf1fbaa918c845b00cf93e01a`.
The captures complete at 5,512 and 6,164 total frames respectively. The
verified-input contact sheet is `build/traversal-01/site/index.html`; it includes
full-capture audio controls, per-interval measurements, and a hash manifest.
The report explicitly makes no gameplay, audio, or release pass claim.

## Observations, not a completion verdict

- Both captures visually reach the next street area. At interval `right_10`
  NES is already there while SNES is still in the initial area; SNES reaches
  the next area later. This does not reproduce the previously reported initial
  75%-of-screen blockage on this candidate, but is not a full traversal oracle.
- At `right_20` both show the right side of the next area. Native imagery then
  changes very little: intervals 20/25/30/35 contain only 3/4/3/3 unique images,
  versus NES 54/53/54/57. Native original-game counter $052B still takes about
  60 distinct values per 120 frames, and no adapter fault is reported.
- The initial visual inspection incorrectly described the HUD at `right_35`
  as truncated to “A”. Follow-up pixel counts and VRAM checks show all four
  letters; this is **not** a demonstrated HUD regression in this capture.
- Equal held-input durations do not mean equal game positions or encounters.
  Raw $DC/$DD bytes are shown for diagnosis only, not asserted as a validated
  scene identifier or monotonically increasing world position.

The next task is to identify the earliest divergent state/rendering in this
reproduction and validate a positional/scene oracle against original behavior.
Do not infer a frozen CPU from a nearly static picture or a working game from
an advancing NMI counter.

## Reproduce

Run `tools/benchmark_capture.py --scenario traversal` for each system, using
the same `--title build/reference-title-05 --walk build/reference-walk-02`
templates and separate output directories. Then:

```sh
python3 tools/traversal_report.py --reference build/traversal-01/nes \
  --candidate build/traversal-01/snes --out build/traversal-01/site
python3 -m unittest discover -s tests
```

Report generation verifies both complete captures, PCM-derived audio metrics,
scheduled inputs, per-frame RAM, phase snapshots and screenshot hashes before
copying media. Forty-eight unit tests pass, including missing/changed/truncated
RAM negative controls. Normal quality reporting still rejects non-baseline
scenarios. The new diagnostic does not weaken existing release gates or change
the runtime ROM. Rivalmage was not changed.

## Follow-up: VRAM and direction reversal

Traversal captures now retain 64 KiB SNES VRAM per phase. Snapshot paths, sizes,
and hashes are verified. In `build/traversal-vram-01/snes`, the HUD nametable
row matches the prepared row byte-for-byte at intervals 15/20/25/35; glyph tile
data and palette staging are unchanged. The rerun has identical per-frame RAM,
video hashes, and full PCM hash to the first traversal, despite the extra
read-only snapshots. The four HUD glyph cells have 20/12/24/13 bright pixels,
including all four letters, at `right_35` and the later reversal checkpoints.
The OAM snapshot cache also matches the original sprite shadow at the examined
checkpoints; those samples do not support a stale sprite-cache explanation.

`traversal-recovery` adds 1,440 frames holding Left after the long Right hold.
Both verified captures in `build/recovery-01` complete. Native moves left,
scrolls, and returns to the prior area: its camera bytes progress from FF00
through 2900, wrap into the prior area (FF01), and reach 3501. This disproves a
stuck-player interpretation of this particular nearly static interval. It does
not prove all right-edge behavior or encounters are correct.

At the end of the same reversal duration NES reaches the school entrance
(camera bytes 0000), while SNES remains farther right (3501). This is visible
evidence of the remaining traversal speed gap; do not reduce it to an NMI-rate
comparison. The paired contact sheet and audio are at
`build/recovery-01/site/index.html`. Forty-nine unit tests pass, including
altered/short/unsafe-path VRAM controls and reversal schedule checks.
