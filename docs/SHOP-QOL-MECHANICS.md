# Shop QoL: verified mechanics before presentation changes

[Original NES / current SNES comparison](http://127.0.0.1:8766/shop-qol-mechanics-review-01/)

The untouched US NES ROM gives repeated combat-stat gains, not a one-time
per-food permanent bonus. Ordinary-input replays bought and consumed Waffles
(item 94) twice in the same café. Both the original and sprite-copy candidate
3252 changed Agility and Strength from 15 to 16, then from 16 to 17. Money went
from $20.00 to $15.90 to $11.80. Neither replay edited RAM or restored a state.

The original game already displays `AGILITY 1 UP.` and `STRENGTH 1 UP.` inside
the shop. The SNES candidate reproduces both messages on both purchases: zero
pixel differences in the fixed dialogue region at four selected checkpoints.
This is not a claim that every shop/item dialogue is qualified.

The preceding encounters differed, so initial stamina was NES 31 versus SNES
38. Recovery and Max Power changes are retained independently, not forced to
match. Original stat application at PRG $92A0..$935D adds to the current stat,
caps combat stats at 63, and converts excess stamina into Max Power through
integer division by four, capped at 127. The complete two-purchase result is
stronger evidence against the one-time rule than a reading of that routine alone.

## Implemented now

- `capture_shop_qol_mechanics.py`: a source-bound two-consumption replay, separate
  combat/recovery snapshots, input/fault checks, and capture wall time. Fresh NES
  capture plus verification took 8.31 seconds; SNES took 10.92 seconds.
- `review_shop_qol_mechanics.py`: revalidates original capture bindings, checks
  summary data against actual RAM snapshots, requires both purchases to grant
  Agility/Strength, checks dialogue pixels, and rejects a first-use-only mutant.
- `shop_qol.py`: executable, balance-neutral **model only** for independent P1/P2
  consumption history and actual stat deltas. Five focused tests pass. Browsing
  does not mark an item; confirmed consumption does, even when stats are capped.

No new in-ROM marker or preview UI has been installed. No game balance, economy,
equipment, save/password behavior, or hardware state was changed. `TRIED` means
previously consumed by this player, never bonus exhausted. It must not imply
repeat purchases are useless. Any remaining-benefit preview must account for
stat caps and recovery independently. The existing dialogue can remain the
authoritative actual-result display.

## Next implementation boundary

After the marker semantics are chosen, hook confirmed consumption (not purchase,
take-out, cancellation, or equipment activation), keep P1/P2 history independent,
and render a minimal NES-style indicator. Test actual ROM execution, per-player
history, repeat gains, caps, take-out, cancellation, shop re-entry and persistence.
The Python history model is not a substitute for those runtime tests.
