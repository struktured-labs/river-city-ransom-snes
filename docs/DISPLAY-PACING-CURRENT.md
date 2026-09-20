# Confirmed one-/three-frame camera presentation jitter

This follows the unpromoted line30 experiment. That previous goal turn was
progress: an actual safe-boundary change was tested and its mixed timing
benefit prevented an unjustified deployment. This turn establishes a concrete
remaining pacing defect rather than using average simulation speed as a proxy.
No game ROM, hardware input, Rival restart or OBS setting changed.

## Complete park renderer measurement

`display-cadence-nes-648` is a fresh original-NES execution. The host observer
records every fetched pixel group entering the background shifter for lines
32..191 in frames7000..8548. Its complete8,548-frame timeline and PCM are
identical to the independent normal capture. The existing full-route SNES
renderer observations likewise match their own independent normal captures.

`audit_display_cadence.py` checks every group/line, rejects duplicates, missing
coverage and split cameras, then records every displayed position and complete
hold interval in the two fixed park phases. Long stops are **not** discarded.
Leading/trailing partial holds are censored explicitly; blank/transition
boundaries are listed individually. Discontinuous measured sequences fail
rather than joining frames across a gap. The initial all-phase attempt correctly
failed because the NES park-entry prefix contains17 rendering-disabled frames;
the final report uses register/transition telemetry to identify these boundaries,
not favorable pixels or observed camera values.

| Park return | One-frame holds | Two-frame holds | Three-frame holds | Uniform2px 1/3 or3/1 pairs |
| --- | ---: | ---: | ---: | ---: |
| Original NES |0|163|0|0|
| Current Rival ROM34835f8 |26|94|25|19|
| Unbranded parent608 |25|96|24|18|
| Unpromoted line30 candidate646 |25|96|24|22|

Other holds—including the NES178-frame stop—remain in the report. Encounters
and input durations differ, so this table is **not equal-work combat speed**.
On the outward trip NES has three1/3 pairs, versus12 for the branded port,
11 for608 and9 for646. The line30 change does not establish an overall pacing
improvement merely by reducing frame-end warning counts.

Full results: <http://127.0.0.1:8766/display-cadence-651/>.

## Exact instruction-to-screen counterexample

`display-pacing-cpu-650` captures every instruction in frames7400..7465 of
the unchanged parent608. Its complete8,629-frame timeline and PCM equal the
normal core. `audit_pacing_case.py` binds the actual pre-`STA $F6` accumulator,
beam and absolute clock to all160 rendered street lines. It verifies the
linked opcode preimage, one actual commit at each selected frame with no
intervening commits, and a constant high camera bit through the entire window.

| Camera | Actual store frame/line/cycle | First displayed frame |
| --- | --- | ---: |
|79|7440 /30 /870|7441|
|81|7442 /28 /794|7442|
|83|7444 /35 /662|7445|

Producer frame intervals are **2,2**; presentation intervals are **1,3**.
The middle update reaches the early-copy window, whereas its neighbors do
not. This is an actual pacing counterexample, not a long hold caused by a
stopped player. The fixed regression report deliberately remains **FAIL**.
It does not establish every jitter cause or explain the separate audio-pop
complaint. All seven surrounding complete screenshots are retained unedited.

Counterexample: <http://127.0.0.1:8766/display-pacing-case-654/>.

The instruction trace also shows main iterations starting at lines52..88 in
this window, and camera completion ranging across the drawing boundary. The
next optimization target is producer/interrupt work and its phase relative to
that boundary—not simply widening the camera-copy window or adding a frame
of input latency to conceal jitter. Any candidate must retain original game
ticks, audio service, clean scene loading and the existing status/shop gates.

541 Python tests pass. New tests detect a shifted single display frame creating
a1/3 pair, preserve long stops/wrap, reject missing/duplicated renderer coverage,
check every NES pixel group, and reject variable producer motion masquerading
as the fixed-cadence counterexample. No acoustic or full-speed release pass.
