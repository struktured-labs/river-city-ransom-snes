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
- At native `right_35`, the HUD name is truncated to “A”. This is a retained
  visual regression, not a passing gameplay result. The cause is not yet
  established. Enemy collisions, death state, mapper/raster effects, and
  rendering divergence require investigation using the retained RAM/images.
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
