# Vertical PPU command pointer cache: faster, not yet promoted

Offline candidate2715 SHA256:
`58b8e3bbf5029572fc607cce1754997e9ac523a4ebf155c1f23d266186fb6038`.
Parent is masked-budget2696. Rival remains on harmonic splash2648, untouched.

[Measured copy costs, unchanged stalls, failed route, native audio and collages](http://127.0.0.1:8766/ring-stride-review-2733/)

## Implementation

The ring copy's existing pointer cache handles increment-one writes only.
Vertical20-byte column commands in the failed combat interrupt repeatedly
resolve the same CIRAM page for stride32 writes. The trial resolves the
physical pointer once per page, updating its low byte directly between page
crossings. All writes, comparisons against existing shadow bytes, dirty-row
and mirror-alias marking, ring index, PPU address and write counts remain.

Eligibility is binary arithmetic, stride32, count1..32, and logical starting
PPU high byte$20..$3A. That bound keeps the entire run below palette RAM.
Zero-as256 counts, longer runs, palette/CHR destinations, increment-one and
decimal-mode callers take the unchanged original routine. No new WRAM scratch
is allocated. The final cached pointer equals the old last-written pointer,
not the next address. Existing return code restores DP/flags and interrupt
policy; original NMI/bank critical sections remain masked.

Only eight five-byte entry trampolines, eight256-byte helpers in verified
FF-filled$6900 space, and checksum change. Global code addresses, game timers,
command budgets, graphics and audio data remain unchanged. Build2714 failed
its preimage check because the builder initially encoded PHD incorrectly;
no changed cartridge was produced there. Corrected2715 is the tested build.

## Executed correctness and actual time

Oracle2727 copies actual parent/candidate runtime bytes into fixtures at their
real addresses, without relinking the routines under test.111 parent/candidate
cases compare all128KiB WRAM except dead stack bytes and fixture heartbeat.
Saved A/B/P/X/Y/DP/DB/SP outputs, original game RAM, pointer scratch, source
ring, all PPU shadow bytes, dirty flags and counters must match. Ninety cases
also pass an independent CIRAM/dirty/ABI calculation. Cases cover logical and
physical page boundaries, both mirroring modes, attribute rows, ring wrap,
unchanged data, zero and long counts, decimal flags, palette/CHR fallback,
and mirrored runtime banks. A binary wrong-stride mutant fails the independent
oracle. The old2716 invocation used90 frames, below the smoke runner's minimum;
2717 preceded the added source-authentication checks.2727 is the current report.

Timing2729 executes two exact oracle cartridges under a same-core neutral
instruction observer. Full fixture RAM matches with tracing on/off. Measured
routine entry through caller return:

|20-byte vertical command | Parent master clocks | Trial master clocks | Saved |
| --- | ---: | ---: | ---: |
|Start$2000 |44,214 |33,424 |10,790 (24.4%) |
|Start$20FF, page crossing |44,446 |34,108 |10,338 (23.3%) |

These are bounded routine costs, not a whole-game speedup.

## Saved-state stalls are NOT fixed

Checkpoint2718's frame2236 is inside the ring routine, so the cross-ROM guard
rejects that replay before execution. Earlier checkpoint2724 at2234 is used
instead. Same-ROM controls2725 and2721 reproduce90 frames exactly; trials2726
and2723 require the exact freshly rebuilt patch, identical128KiB starting
WRAM and all CPU registers, and recorded two-port input callbacks.

Both targeted missed interrupts remain: completion is still2240 and4318.
The known failure pictures match through those endpoints. This is not a causal
frame recovery, even though instruction work is reduced. The independent
two-player campaign2719 is fully observer-neutral; sustained attacks has1,752
stable two-frame intervals and no longer gaps. Running/jumping has1,744
two-frame intervals and two three-frame gaps2249–2252 and4314–4317. It still
fails. Different encounters prevent interpreting3→2 gaps as proof of recovery.

## Full-route failure retained

One-player route2728 reaches the park but Alex loses all power during the
west sweep. Frame9360 shows the loss message; original RAM remains room3 at
x510 through9360, then transitions into room2 at9387. The input-only waypoint
policy intentionally stops issuing directions in the wrong room, and times
out at10,428 frames. The final image is the mall, not the completed park route.
This is incomplete navigation, not a fault-latch or proven gameplay corruption;
the changed encounter is not equivalent to the parent encounter.

DSP2732/control2731 repeat the same incomplete route. No successful whole-route
scrolling or audio qualification is claimed, and the complete-route gates were
not weakened to accept these recordings. All artifacts remain for audit.

Full suite:1,185 tests pass (`/tmp/rcr-tests-2730.log`). New tests check patch
scope/preimages/repetition, independent unchanged-boundary behavior, corrupted
shadow/flags/counters/ABI rejection, and explicit fallback scope. Web review2733
has116 verified source bindings and21 verified artifacts; browser collage was
inspected. No hardware/OBS/controller changes or promotion.

## Next

Keep the bounded optimization available, but do not substitute it for the
remaining interrupt fix. A retained original body entered near line239 can
still cross the full blank even with every graphics producer deferred. Further
PPU command/adapter reductions and correctly accounted interrupt scheduling
need same-state proof. Repeat whole-route, menus, rendered-camera and native
audio qualification before promotion. Physical holds and perceptual pops remain
open alongside full original-speed parity.
