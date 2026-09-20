# Lower-cost packet logging: diagnostic still withheld

September 18, 2026. No hardware/OBS/controller changes. Rival's production
cartridge is unchanged. [Combined audit and failed-load collages](http://127.0.0.1:8766/audio-packet-cost-review-1567/).

Follow-up: [interleaving packet writes with acknowledgement waits](AUDIO-PACKET-INTERLEAVING.md).

The previous [logger](AUDIO-PACKET-LOGGER.md) established actual SRAM ring
operation and exact retained SPC receipts, but added significant CPU work.
Two isolated implementations now reduce that cost without changing its format:

1. Word-copy1547 uses16-bit copies and XORs pairs before folding the result
   into the same8-bit XOR check. It retains the original register contract.
2. Caller-aware1560 also removes duplicate A/B/X/Y saves. The outer audio
   bridge already saves/restores the game registers. This reduced-contract
   helper preserves P/DB/DP and register widths but treats A/B/X/Y as scratch.
   Its builder requires the exact68-byte caller, prologue and epilogue. It is
   **not** a generally substitutable `spc_frame` helper. Tests mutate every
   caller byte and require rejection. Upload initialization remains identical.

Both are separate diagnostic cartridges. Production sources, SPC engine,
graphics and the deployed ROM remain unchanged.

| Logger | Measured elapsed master clocks | Median | Measured spans |
| --- | ---: | ---: | ---: |
| First1539 | 3,898–4,270 | 4,016 | 4,568 |
| Word1547 | 3,086–3,432 | 3,138 | 4,568 |
| Caller-aware1560 | 2,846–3,166 | 2,898 | 4,568 |

Measurements cover after the existing sender returns through before the logger
RTS. They include refresh/events, exclude additional call/return overhead and
are not matched-work comparisons across identical encounters. The static
instruction reductions explain the direction, but no exact full-game speedup
is inferred from these medians.

## Correctness and endurance

Each variant ran5,000 frames under normal, receiver-observed and CPU-timing
cores. Within each variant, all three complete WAVs, final WRAM, SRAM, frame
metadata and screenshots match. Each has4,606 independently observed complete
SPC packets; all4,095 retained SRAM records match byte-for-byte, with511
overwritten records disclosed. Actual saved-byte and receiver-byte corruption
controls fail. No reported native faults or retained timeouts.

Word-copy endurance1556 ran70,000 frames, counted69,568 packets and retained
4,095 structurally valid records. There was one native16-bit NMI wrap, at
zero-based frontend frame65967. Counts never decreased or advanced
by more than one per frontend frame. There were98 post-start frame intervals
without a newly completed packet, retained in the frame trace, not hidden.
65,473 overwritten records are unavailable. This longer run lacks independent
SPC receipt matching and therefore certifies structure/wrap operation only,
not every transmitted payload or cadence throughout the run.

## Gameplay regressions: pass and fail

Word-copy normal1551, exact-PC main1554 and raster1558 complete8,861 frames;
main/raster observers are neutral. Cadence1559 passes3,550 stable loops across
four rooms:598/1,746/475/731. All selected iterations and consecutive stable
starts span two NMIs/frames. Park camera holds are east212×2+9×14 and
west153×2+4×14; there are no short irregular holds. Long holds and exclusions
remain in the report. Different encounters mean this is not equal-work or
whole-game original-speed proof.

However, **both variants fail the unchanged NES room-entry gates**. The first
room appears at offset8 instead of7; the other two appear at7. Total visibility
and exact fixed-offset background gates also fail. Collages1553 and1566 are
published, not replaced with favorable samples. The parent final image/RAM/PCM
also differs. The caller-aware build has not separately repeated the main/
raster cadence qualification; the word-copy pass must not be transferred to it.

An attempted raster1555 used a core without the requested trace feature and
failed with no capture receipt. Its attempted audit1557 also failed. Those are
not evidence. Raster1558 uses the verified raster core and authenticates its
actual trace. No failed artifacts were removed.

## Decision

Neither variant is deployed or certified timing-neutral. The remaining
physical audio silence is still unexplained. Further gains should examine
whether logging can use existing sender-wait time, or be strictly bounded to
an explicitly instrumented gameplay interval with measured disturbance. Merely
adding the faster logger after every transfer still perturbs load timing and
does not satisfy the user's original-speed requirement.
