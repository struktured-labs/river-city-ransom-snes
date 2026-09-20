# Alley-load speed: compare the same counters and retain elapsed time

[Original/candidate collages, native audio and counter evidence](http://127.0.0.1:8766/load-counter-review-2356/).

Candidate remains compact-pair2242, SHA
`f7f8e725acaaef5592ededba9149ce17e1d7a43767a8deae739f825270c6c829`.
No ROM edit, Rival restart, controller input or OBS change in this investigation.
The previous goal turn made progress by rejecting the DC audio trial using
recorded commands. This turn resolves an ambiguity in the remaining combat
timing report instead of attempting to accelerate an original-game wait.

## The counters were not like-for-like

The old combat audit calls both values `nmi_advances`:

- NES: the original game's byte at `$010B`, sampled at main completion.
- SNES: the delta of native `$1C04/05`, incremented at the native NMI entry.

These agree in the measured stable loops but need not during loading.
Fresh host-only observations inspect the same `$010B` on both systems at
main start/input/finish and immediately before/after the original `$E05C`
`STA $010B`. All observed instruction preimages are checked. The relocated
SNES start first marks the main thread at `$1CE1`, then performs the original
counter clear; the observer checks that exact byte sequence, not a assumed
`LDA #0` at its entry.

| Event | Relative frame, NES | Relative frame, SNES | `$010B`, both |
| --- | ---: | ---: | ---: |
| Main start |0|0|2|
| Input call after main clear |0|0|0|
| Load-end counter-clear instruction |13|13|1|
| Immediately after that clear |13|13|0|
| Main completion |15|15|2|

NES loop2101–2116 and SNES running/combat loop2556–2571 therefore both span
**15 physical frames**, not two. SNES native NMI-counter delta8 is retained
in the historical report; it is not an8-versus2 original-game tick slowdown.
Frame snapshots independently retain the load's game-counter history.

## Deadline checks, not a blanket loading exemption

The first0→1 transition is selected from observed game state, never by choosing
a favorable duration. It must contain the first alley rendering-enable edge.
The fresh NES/SNES event sequences match at every relative frame. Entire load
latency remains measured: room-change and rendering-off to first scenery are
20 frames in both, and all40 fixed background/fade offsets match exactly.

The separate reference-context gate admits only this specifically matched
load interval. All remaining measured running/combat loops must still finish
in two frames at game tick2. Contiguous starts/completions and phase-boundary
coverage are checked independently; no interior loops may disappear. All1,655
loops across the seven requested combat phases pass these scoped checks.
Mutations adding one elapsed load frame or one ordinary gameplay frame fail.
The old strict report remains unchanged and FAIL; it is neither overwritten
nor presented as a newly passing two-frame-only result.

## Source and observation controls

- Fresh NES2352 matches all8,548 frames and PCM from same-core normal2271.
- Fresh SNES2353 matches all4,913 frames and PCM from same-core combat2243.
- Existing emulator host hooks are reused; no core/ROM/state/input mutation.
- Three new tests check both trace ABIs, exact opcode preimages, reset failure,
  missing input, extra elapsed time despite a reset counter, and missing/late
  ordinary loops.
- Preliminary2354 is superseded after adding the parser regression test.
  Final2356 binds the final sources and tests.

Input policies and actor histories still differ between platforms. This is a
matched first-alley-load deadline and stable-loop comparison, not equal CPU
work, full-game speed or physical-hardware certification. Existing render,
forward-room and same-state school-return evidence remains separate. Fresh
current-candidate menu/status regression is the next qualification step.
Physical audio popping remains open; the rejected DC trial is not included.
