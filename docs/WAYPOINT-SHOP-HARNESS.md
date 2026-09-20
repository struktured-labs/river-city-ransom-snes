# State-aware café traversal and menu regression

The timing-changing candidates were missing the café under the old fixed
movement script. New **separate** waypoint scenarios navigate using ordinary
controller input and preceding-frame observations. The old fixed-input park,
movement and shop scenarios remain unchanged; this is not a relaxation of their
timing gates or a replacement for same-input speed comparisons.

`tools/traversal_waypoints.py` has no emulator handle or memory-write path.
It observes original RAM (room `$42`, coordinate arrays `$388/$390/$398`,
task `$100`, menu/pause flags `$3E/$3F`) and a fixed original-font cursor shape.
The common policy is identical for NES and SNES:

1. Retain the existing jump/right route prefix.
2. Steer toward the alley doorway and use Up, with brief B presses to clear
   obstructing goons. Stop after three consecutive room-2 gameplay observations.
3. Steer to the café, enter with Up, and explicitly dismiss its greeting with
   short A presses. Stop when the original item cursor is visible for three
   consecutive frames in the café menu state.
4. Execute the existing purchase/YES-NO input tail unchanged.

Navigation is bounded to 1,920 frames for the mall and 1,200 for the café.
Timeout retains an incomplete capture and stops the scenario; it cannot be
reported as a menu-test pass. No teleporting, RAM edits, savestates, input
search against the reference outcome, or emulated overclocking is involved.

## Arrival is not readiness

The first version stopped on café room/menu state alone. Both systems entered
the café, but the first purchase-test A press merely dismissed **“May I help
you?”**. The old fixed script happened to dismiss that greeting while Up was
still held. Failed attempts `waypoint-shop-*-194/195` are retained, with their
exact original policy saved as `build/waypoint-policy-v1-194.py`; its hash
matches the receipts. They are not successful purchase tests.

The corrected policy requires the original item-cursor shape at fixed
`(96,72)..(104,80)` coordinates. Its mask comes from authenticated original NES
`shop-repeat-nes-91/observe_shop.png`, not an approximate image-search match.
The final audit independently checks café name, item list and ready dialogue
against that authenticated reference before running any menu oracle.

## Evidence integrity

Waypoint captures retain every frame, original 2 KiB RAM, requested/delivered
buttons, cursor observations and the policy source hash. The verifier:

- Reconstructs each input from the **preceding** frame, not the resulting state.
- Binds every cursor observation to its PNG and raw rendered-pixel hash.
- Checks original RAM against the frame RAM hash.
- Requires stopping at the **first** three consecutive matching observations.
- Rejects changed policy source, forged cursor data, altered input decisions,
  premature success, and false timeout claims.

Seven policy tests and four end-to-end synthetic evidence tests cover those
rules, including mutations with recomputed timeline hashes. Full suite:
**332 tests passing**. Existing fixed-input `park-ring-pointer-guard-192`
still validates with 9,407 frames under the updated verifier.

## Executed results

Candidate is the interrupt-safe combined build
`build/ring-pointer-guard-native-192/native-cpu.sfc`, SHA-256
`5ac817a86c27c657d0dac9bf3d09677ea87057cee597c2184647e62f3abfccc5`.

- [Two consecutive purchases](../build/waypoint-repeat-audit-198/index.html):
  all ten existing fixed-region pixel and shadow/VRAM glyph checks pass.
  Captures: `waypoint-shop-repeat-{nes,snes}-196`.
- [YES → NO → YES → NO → confirm NO](../build/waypoint-no-audit-198/index.html):
  all nine existing checkpoints and money checks pass.
  Captures: `waypoint-shop-no-{nes,snes}-197`.
- The old stale-cursor ROM (`shop-repeat-coverage-90`, SHA
  `59bd61c978077e29581aa78d13f8cf52c6239894ae01675b603a9493876cacfe`)
  reaches the same café and **fails** the unchanged NO-menu oracle. Its
  capture and screenshots are included as the negative control above.

Observed waypoint durations are 234/426 frames on NES and 238/431 on the
candidate (mall/café). These are independently evolving encounters with a
feedback policy: **not** a same-input speed ratio or proof of original speed.
`tools/audit_waypoint_shop.py` uses the existing strict menu analyzers without
changing their pixel regions, glyph requirements, or money expectations.

No ROM changes or Rival restart in this harness work. The six late park audio
packets, worst 2.0126-frame interval, and pause-close phase discrepancy remain
open. The harness now allows actual café regressions to be tested while
continuing speed/interrupt work; it does not certify hardware audio.

## Reproduce

```sh
python3 tools/benchmark_capture.py --system snes \
  --core .deps/snes9x/libretro/snes9x_libretro.so \
  --rom build/ring-pointer-guard-native-192/native-cpu.sfc \
  --title build/reference-title-05 --walk build/reference-walk-02 \
  --scenario traversal-waypoint-shop-repeat --out build/waypoint-repeat-new
python3 tools/audit_waypoint_shop.py \
  --reference build/waypoint-shop-repeat-nes-196 \
  --candidate build/waypoint-repeat-new --cafe-reference build/shop-repeat-nes-91 \
  --out build/waypoint-repeat-audit-new
```

For NO testing, use `traversal-waypoint-shop-no`; the audit also accepts an
optional `--negative` capture of the same waypoint scenario.
