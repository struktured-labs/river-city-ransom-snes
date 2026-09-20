# Saturating shift: less load work, not a qualified release

[Measured CPU work and before/after frames/audio](http://127.0.0.1:8766/saturating-shift-review-2119/)
· [Combat failures](http://127.0.0.1:8766/saturating-combat-review-2108/)
· [NES entry/fade comparison](http://127.0.0.1:8766/saturating-entry-2107/)
· [Whole-route renderer](http://127.0.0.1:8766/saturating-render-audit-2118/)

Offline newer-scheduling candidate2087:
`55b7951e004f0ed12b08a2b7644fb7031bbace5980fe9bdf4b0d0c11370eeff6`.
Controlled parent1947 branch2088:
`9b84a5deeeb435898430067a96db690b657c88919b58a0c1350c0cb3b11d1d39`.
Neither was deployed. Rival retains splash-only57a046b683c4; no OBS/controller
or hardware state was changed in this work.

## Actual code change

`build_saturating_shift_trial.py` patches17 bytes atC1..C8:C3B9 and installs a
64-byte helper in previously FF-filled C1..C8:7FC0, plus checksum. The builder
refuses occupied helper space, changed continuation, changed original loop or
repeat patching. Five-shift and direct body entry locations remain intact.

The observed X=0 entry originally performs256 arithmetic right shifts on a
16-bit value. Its result is entirely sign-filled after16 shifts. The shortcut
directly produces that result and the original final A/X/P/operand state.
Nonzero counts use the existing counted loop. No graphics, timer, interrupt
handler, controller or SPC changes are included. Default build remains unchanged.

## Executed equivalence

Oracle2101 executes983,040 cases in actual Snes9x: every16-bit input crossed
with eight D/I/V combinations for X=0 (rotating through eight banks), plus
counts1/5/15/16/17/127/255. A, hidden B, P, X, Y, stack and both operand bytes
match the original instructions. Wrong sign source, wrong sign-fill value and
wrong final zero flag are rejected as executed mismatches, not tool failures.

The exact assembled helper and hook are checked against all eight banks of
candidate2087. Review2119 additionally binds the2088 helper to this oracle's
helper. Earlier review2112 omitted that explicit cross-candidate helper check;
2119 supersedes it. The old report is retained, not silently rewritten.
This is E=1, DP=DB=0, without injected interrupts; not all256 counts crossed
with all flags/banks, nor an interrupt-race proof.

## School-return evidence

Fresh normal/observed main2102 and instruction2105/2106 runs are neutral over
the entire4,913-frame episode: video, RAM, input and native PCM match controls.
The parent replay is1948/1950/1952. Encounter timing differs between builds;
this is not an identical-state causal comparison or NES speed ratio.

| Measurement | Parent1947 | Shortcut2088 |
| --- | ---: | ---: |
| School-return loop | 26 frames | 23 frames |
| Whole-loop elapsed master clocks | 9,314,156 | 8,244,286 |
| Shift calls | 45 | 45 |
| Zero-count / five-count entries | 38 / 7 | 38 / 7 |
| Shift inclusive elapsed clocks | 1,308,884 | 12,330 |

Whole-loop saving is1,069,870 clocks (about11.5%). These elapsed costs include
interrupts/DMA; savings are not additive CPU-exclusive timings. FC73's original
self-wait remains, and its elapsed cost actually increases in this replay.
It is not subtracted from acceptance or patched away.

**The older-scheduling branch remains rejected.** All its measured outliers:
2556–2571 (8 ticks),2571–2574 (3 ticks),4110–4133 (7 ticks).
The extra3-tick interval is retained as a regression, not hidden by the faster
school-return interval.

## Newer scheduling branch2087: full-route checks

Uninterrupted route2104 completes9,225 frames. Longer/shorter traversal length
is not a speed ratio: encounters and movement outcomes can differ.

- Room-entry2107: all three rooms have first scenery at NES+7 after rendering
  enable; every one of40 fixed fade offsets matches. Room-change visibility
  is19/25/26 frames; rendering-off visibility20/26/26, all no later than NES.
- Main2110/2111, audit2117: all3,739 stable loops take2 ticks. No short irregular
  park holds. **Thirteen14-frame holds remain** (ten east, three west); stable
  cadence passing does not waive these or excluded transitions.
- Renderer2114/2115, audit2118: all7,616 eligible frames covered,6,655 held-camera
  frames checked; zero missing coverage, splits or stale-camera failures.
- DSP2109, audit2113:8,783 actual received packets,1,622 restarts, zero late
  configuration writes. Raw DAC equals4,918,005 native stereo PCM samples;
  peak6,286 and zero clipped samples. Late-write negative control rejected.
  This does **not** establish pop-free sound, original-NES waveform fidelity,
  absence of stale DSP latch behavior, or physical capture performance.
- Both combat policies2103: full normal/observed equality. Sustained attacks:
  1,661 loops pass. Running/jumping:1,655 loops; strict gate still fails at
  2556–2571 (15 frames,8 ticks). The school-return transition does not occur
  in this route, so its absence is not evidence it was fixed in this branch.

Same-core normal/observed controls exist separately for DSP, main, renderer,
combat and instruction traces. No speed/audio acceptance thresholds changed.
Seven new patch/profiling tests pass; full suite1,038 passes in2116.
Two refused invocations (wrong observer core and misspelled renderer environment
key) stopped before capture; corrected fresh invocations produced the evidence.

## Next required work

The [controlled school-return comparison](CONTROLLED-SCHOOL-RETURN.md) now
confirms the saving on identical starting state, but its new NES reference
exposes a two-frame return-fade publication delay. Fix that scheduling path and
qualify menus again before any promotion. Remaining strict load timing, retained
long camera holds and nonzero audio pops need original-game/physical evidence.
Do not deploy merely because arithmetic, stable cadence or DSP transport pass.
