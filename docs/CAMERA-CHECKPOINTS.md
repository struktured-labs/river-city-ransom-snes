# Camera-matched scrolling checkpoints

The latest left-clipping candidate was captured with the unchanged right-then-left
scenario in `build/left-clip-recovery-01/snes` (7,051 total capture frames).
Reference: `build/recovery-01/nes` (6,952). These are phase-driven sequences,
not synchronized gameplay; enemies and encounters differ.

`tools/camera_audit.py` builds explicit checkpoint pairs only after verifying
the captures, original ROM binding, delivered inputs, and checkpoint RAM.
Both the 16-bit game camera at DC/DD and nine-bit street scroll at F6/3D must
match. No pixel search, offset adjustment, or sprite masking is performed.
Unit tests reject disagreement in either camera byte or the scroll's ninth bit.
Equal camera registers alone do not independently establish room identity.

For candidate SHA
`74fe0decfe571e9f43897ffd54aa914db4ee50e1f7947d3b9e0591f3e53326dc`:

| NES checkpoint | SNES checkpoint | Camera | Differing pixels in x=0..255, y=32..111 |
| --- | --- | ---: | ---: |
| right_00 | right_00 | 0 | 191 |
| right_09 | right_06 | 511 | 0 |
| right_14 | right_12 | 255 | 29 |
| left_04 | left_04 | 0 | 0 |
| left_05 | left_05 | 511 | 119 |

These pairs were selected by equal camera positions at common traversal
checkpoints, not by minimizing pixel differences. Differences in the first,
third, and fifth pairs occupy small actor-height regions near the bottom of the
fixed strip; they remain visible in the report and are not counted as passes.
The two exact matches provide pixel evidence beyond merely observing changing
scroll counters. They do not certify every scroll position, room transition,
actor coordinate, or gameplay speed.

The read-only reference's RAM sprite page $0200 matches captured OAM in many
frames but not all (including mismatches at frames 1500, 1800, 3000, 3300, and
3600 of `reference-walk-long-01`). It is therefore not yet a sound basis for
automatically excluding sprites from pixel comparisons.

Generate the diagnostic web audit with:

```sh
python3 tools/camera_audit.py \
  --reference build/recovery-01/nes \
  --candidate build/left-clip-recovery-01/snes \
  --pair right_00:right_00 --pair right_09:right_06 \
  --pair right_14:right_12 --pair left_04:left_04 --pair left_05:left_05 \
  --out build/left-clip-camera-02
```

The HTML includes complete screenshots and unmasked difference strips. All
61 unit tests pass. This turn makes no ROM change or Rival deployment; speed,
audio fidelity, and comprehensive scrolling validation remain unfinished.
