# Incremental sprite preparation · not deployed

`--experimental-sprite-delta` preserves the original sprite bytes and SNES
mapping while converting changed entries. The initial implementation below
updated all four output bytes for any entry change. The current experimental
implementation [updates two field pairs independently](SPRITE-PAIR-EXPERIMENT.md)
and uses short WRAM accesses with an explicitly restored data bank.
Initial generation and OBJ pattern-half changes still force every entry to
convert. A clean translated OAM dirty flag skips comparison only after checking
those invalidations.

The default remains off. The existing all-sprite unrolled converter is retained.
`snes/sprite_delta.inc` is hash-bound in the native build manifest. No ROM art,
game logic, audio engine, or SNES overclock setting changes in this experiment.

## Executed graphics checks

The following retained results describe the first implementation. The current
26-case oracle and five negative controls are linked in the pair experiment.

```sh
python3 tools/check_sprite_delta.py \
  --core .deps/snes9x/libretro/snes9x_libretro.so \
  --out build/sprite-delta-oracle-new
```

The [retained oracle report](../build/sprite-delta-oracle-160/report.json) includes
18 consecutive asset-free state changes: all 256 original attributes in both
pattern halves; identical dirty OAM; individual Y, tile, attribute and X changes
at first/middle/last entries; clean OAM; pattern-half change without OAM dirtiness;
and initialization repeated after caches are populated. Every staged OAM byte,
the complete input cache, hidden unused entries, and the high OAM table are
compared against an independent Python mapping.

Two executed negative controls reject missing pattern-half invalidation and
ignored attribute/X changes. The full native producer/consumer synthetic pixel
oracle also passes, including a second-generation sprite move. These checks
prove graphics conversion, not whole-game timing or shop reachability.

## Park experiment

| Build | Late stable-park packets (>1.5 frames) | Active run observations | Zero-NMI-step pairs within run phases |
| --- | ---: | ---: | ---: |
| Parent, `park-execution-audit-154` | 41 | 504 | 35 of 495 |
| Looped delta, `park-delta-audit-157` | 16 | 646 | 11 of 634 |
| Fixed-offset delta, `park-delta-audit-160` | 15 | 533 | 7 of 523 |

The fixed-offset build is `build/sprite-delta-native-159/native-cpu.sfc`.
[Park screenshots and complete timing report](../build/park-delta-audit-160/index.html).
The worst stable interval is still **1.7694 frames** (parent: **1.7401**), so
the deadline gate still fails. The same inputs produce different enemy states,
room-transition exposure and pause timing. These counts are not a matched-state
percentage speedup and do not establish original NES speed or acoustic fidelity.

## Why it is not on Rival

Fresh pause, shop-NO and two-purchase captures ran on the fixed-offset candidate.
The pause selector matches in eight of nine checked phases, but `pause_close`
does not match its fixed-frame reference. Both shop scripts miss the intended
shop: `shop_confirm_idle_3` is visibly outdoors at the mall. Their fixed
movement durations no longer reach the same door after the timing change.
The menu gates fail and are retained, not relaxed or relabeled as passes:

- [Pause selector](../build/delta-pause-cursor-audit-162/index.html)
- [Shop NO](../build/delta-shop-no-audit-162/index.html)
- [Two purchases](../build/delta-shop-repeat-audit-162/index.html)

Next: add ordinary-input, state-aware traversal checkpoints to establish the
same shop entrance before testing menu content; retain the input/state trace.
Also measure the remaining masked producer costs against actual interrupt
deadlines. Do not ship solely because the count of late packets fell.
