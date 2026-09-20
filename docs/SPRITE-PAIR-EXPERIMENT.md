# Sprite field-pair conversion · experimental, not deployed

Current `snes/sprite_delta.inc` improves the opt-in converter without changing
original graphics, game logic, audio engine, or interrupt policy:

- Y/tile and attribute/X words are compared and updated independently.
- DB temporarily selects `$7E`, allowing short WRAM snapshot/output accesses.
  ROM lookup tables use explicit `$C0` long addresses, and DB is restored.
- Initialization or OBJ-half changes complement every snapshot word once,
  forcing all comparisons to fail. Completed snapshots still equal the input.
  All of this occurs in the already-masked producer; no consumer can see the
  temporary invalidation. The ordinary clean-OAM fast path remains.

The flag remains **off by default**. A fresh default-off rebuild in
`build/sprite-pair-default-control-183` is byte-identical to
`build/status-pinned-171/native-cpu.sfc`, SHA-256
`0555919b60acd05b25a98973292b29f508aefee3128f88a15ab9bc3a3c55613e`.

Experimental candidate: `build/sprite-pair-native-178/native-cpu.sfc`, SHA-256
`7406182e4db1fa9081fe6dbc9895a7f69cafae01b809c59cadc61907d49ba943`.
This candidate includes the pinned Present Status repair, unlike the older
sprite-delta candidates. It does not include the branding wrapper.

## Graphics and CPU-state oracle

[Executed 26-case report](../build/sprite-pair-oracle-180/report.json).
All 544 staged OAM bytes and 256 input-snapshot bytes are checked after each
case. Both OBJ halves cover all 256 attributes, all 256 Y coordinates and all
256 tile values. Single-byte changes, identical dirty input, clean input,
half change without dirty OAM, and repeated initialization are retained.
The full producer/consumer synthetic pixel oracle also passes.

Each call now records returned DB, direct page and accumulator/index/decimal
flags. The fixture normalizes those registers only **after recording** the
return, so a deliberate bad ABI cannot stall the heartbeat and hide its cause.
The earlier lost-DB negative control did stall the heartbeat in
`sprite-pair-oracle-179`; the fixture was improved, not the assertion relaxed.

Five executed mutations are rejected: lost half invalidation, ignored
attribute/X changes, ignored Y/tile changes, lookup in the wrong ROM bank, and
lost DB restoration. The last mutation produces correct sprite bytes but fails
the new ABI checks, demonstrating why a pixel-only test was insufficient.

```sh
python3 tools/check_sprite_delta.py \
  --core .deps/snes9x/libretro/snes9x_libretro.so \
  --out build/sprite-pair-oracle-new
```

## Park timing

[Full park packet/scene report](../build/park-sprite-pair-execution-178/index.html)
and [exact-clock stage report](../build/park-sprite-pair-span-audit-178/index.html).
Same input-only route, 9,412 total frames, no native faults, both original and
candidate reach the park. The existing deadline gate remains unchanged.

| Candidate | Late stable-park SPC packets | Worst interval in nominal frames |
| --- | ---: | ---: |
| Production gameplay parent | 41 | 1.7401 |
| Eight-word comparison experiment | 14 | 1.7288 |
| New field-pair converter | 12 | 1.7065 |

The worst new interval is 609,828 master clocks at raw frames 8555..8557,
`park_04_right_run`. It still exceeds the 1.5-frame limit: **FAIL**.
Different enemy states evolve under the fixed inputs; these counts are not a
matched-state percentage speedup or an acoustic-fidelity verdict.

Within the narrower 7535..8105 raw-frame observation window, long NMI-entry
intervals fall from 43 to 1. Sprite-stage costs are minimum 12,334, mean
13,935.24, maximum 24,376 clocks (parent: 20,306 / 35,066.99 / 54,058).
These are different whole-game executions, not paired identical OAM workloads.

The remaining profiled miss is concrete: NMI at frame 7803 line 240; camera
exit at 7804 line 81; original NMI return line 156; original sound finishes
line 192; audio starts line 197; rows start line 209; sprites start line 235;
return reaches its outside-VBlank poll at line 247. Next NMI is frame 7805
line 240. Original NMI work takes 102,094 clocks in this event, original sound
49,066, row preparation 32,306 and sprite preparation 15,716. Sprite conversion
is no longer the largest contributor in this example.

## Integration checks

Unlike the older fixed-entry delta candidate, this route reaches the café
without modifying the ordinary input script. New captures and existing strict
oracles establish:

- [Two consecutive purchases](../build/sprite-pair-shop-repeat-audit-181/index.html):
  all ten checked prompt phases match NES pixels, shadow and VRAM.
- [YES/NO selection](../build/sprite-pair-shop-no-audit-181/index.html): all nine
  checkpoints match, NO leaves money unchanged, stale-cursor negative control fails.
- [Present Status](../build/sprite-pair-status-audit-181/index.html): opening and
  reopening match original digits and pixels, and displayed values match RAM.
  New reusable `tools/check_status_regression.py` supports speed candidates
  without pretending their ROM diff is only the status repair. The old blank
  build is rejected at both checkpoints with 624 differing pixels each:
  `build/status-regression-negative-181/report.json`.
- [Pause cursor](../build/sprite-pair-pause-audit-181/index.html): eight of nine
  checkpoints pass. `pause_close` has 718 differing pixels. Cursor clearing
  and reopening pass, but the complete strict result remains **FAIL**.

## Pause motion diagnosis

Fresh original NES, production gameplay parent and new candidate captures retain
every frame and full original RAM: `build/pause-motion-{nes,parent,pair}-182`.
`tools/audit_pause_motion.py` compares the same input-relative offsets, using
the unchanged fixed menu region and RGB555 comparison. No pixel shift, image
search, or timing realignment is applied.

[Three-way animation collage and frame hashes](../build/pause-motion-audit-182/index.html).
Original and parent become permanently blank at zero-based input offset 49;
candidate at offset 50. The candidate is one display frame behind through
most of the closing animation. The parent also differs from NES in the early
closing frames; a previously passing single final checkpoint did not prove
the entire animation. Neither discrepancy is hidden or called a pass.

**Rival remains unchanged** on `RCR-SNES-8bcff69.mgl`: the deadline and strict
pause-motion gates have not passed. Full Python suite: 317 tests passing.
Next work should isolate the measured original NMI/sound costs and investigate
the one-frame input/publication phase difference, retaining this faster
converter as an opt-in candidate rather than declaring original-speed parity.
