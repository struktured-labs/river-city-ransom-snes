# Stable gameplay start phase

Follow-up: [timing-plus-noise build799 is now on Rival](MAIN-PHASE-NOISE-RIVAL.md),
after full-route loop accounting and physical audio verification. The results
below describe the earlier783 qualification state.

Candidate783 is an improvement, **not deployed or release-qualified**. Rival
remains on616 (`34835f8…`). No controller input, reset, OBS setting or recording
change was made during this work. The user's standing instruction authorizes
meaningful tested restarts without a permission prompt; the original-speed
benchmark remains a prerequisite.

## Implementation

`experimental_main_phase_line=128` adds a guarded, bounded beam wait before the
existing main-iteration entry. It leaves NMI enabled, preserves incoming
registers/flags and bypasses pause, fade, transition, bank-critical and pending
old-NMI states. It waits only in the early current frame, never through the
high scanline bit into a new frame. The option remains default-off and requires
second-tick preparation. It builds on735's cached-pad and sprite-position work;
the rejected deadline guard and column-fetch optimization are disabled.

The97-byte helper and entry redirects change790 ROM bytes relative to735.
All73 pre-existing global runtime symbols remain fixed. Executed fixtures780
and781 each pass50 real-beam/register/guard cases and reject five mutants,
including an NMI-masking mutant. Patch proofs785 match the fixture and linked
helper after exactly two verified relocations. Disabled778 is byte-identical
to735. Rebuild789 from the current builder is byte-identical to unbranded782:
`f4fc741f670c17b0dba88293980f24c3f47549c73129821ef9f8118cb676460f`.

Branded783:
`39a1b830177f9d70854bd0bb9cd843e3838b83c5d0820ec5c3609dd16dd75cc0`.
Original artwork, Struktured Labs image/ident,240-frame logo hold and controller
mapping remain unchanged. This is not a new bass drop or controller-mode release.

## Why128 rather than96

Phase96 made sampled main starts consistent but still crossed the early camera
publication boundary: stores7802/7804/7806 became displayed7803/7804/7807,
turning2/2 production into1/3 presentation. `main-phase-96-case-779` binds the
instructions, all160 rendered street lines and seven unaltered screenshots.
Its full-route short irregular holds were22 east/0 west. Phase128 moves the
earliest start later to avoid that boundary; it is not an arbitrary change to
the original tick counter or an extra VBlank wait.

## Exact branded-ROM results

All paths below are under `build/`.

| Check | Result | Evidence |
| --- | --- | --- |
| Park route |9,403 frames; normal/renderer timelines and PCM identical|main-phase-128-normal/raster-784|
| Short irregular scrolling holds |0 east/0 west, versus6/7 on744; long stops retained|main-phase-128-holds-787|
| Rendered street |7,785 eligible frames fully covered, no splits;6,840 held frames, no extra stale camera|main-phase-128-renderer-785|
| Room entry |19/28/29 frames versus NES20/31/30; visibility and every fixed-offset background fade gate pass|main-phase-128-entry-785|
| Short movement |Every measured target no later than NES, equal final displacement|main-phase-128-movement-audit-788|
| Present Status |First entry and reopening pixel-exact|main-phase-128-status-audit-788|
| Repeated shopping |Authenticated café and repeated-purchase/cursor oracle pass|main-phase-128-shop-audit-791|
| SPC transport |8,950 actual received packets match|main-phase-128-spc-audit-785|
| PCM discontinuities |No missing callbacks/clipping; maximum step4677/32768 under unchanged0.171656 threshold|main-phase-128-transients-787|

The shop run did not supply a new negative-control capture; its report says so.
The audio audit rejects missing-callback and full-scale-spike controls, but
cannot certify absence of quieter perceptual pops or current hardware sound.

The exact background audit785 remains **FAIL**:802 common positions are exact
and stable samples are no later than NES, but room1 has37 positions against a
64-position minimum. The old same-frame publication requirement also fails
(946 observations). Neither gate was loosened or removed.

## New main-to-display evidence

CPU capture791 is neutral against the complete normal replay. Its14 complete
iterations start at line128; camera stores occur next frame at lines59..92
(`main-phase-128-start-792`). This is a bounded window, not route-wide CPU proof.

The original NES exact-PC observer774 is also fully timeline/PCM neutral.
Its738 complete main iterations put the camera store in the next recorded frame.
FCEU's reported line240 persists throughout VBlank and is not a precise physical
start line. NES CPU cycles are not SNES master clocks.

`main-phase-latency-794` joins those authenticated intervals to actual complete
rendered street cameras:392 original NES changes appear one frame after their
store and three appear in the same frame. All nine covered changed SNES stores
appear one frame later. Unchanged cameras, incomplete windows and ambiguous
boundaries are retained separately. This explains why an end-of-frame RAM
comparison alone does not establish equivalent display latency, but does not
waive the strict gate or prove matched combat/input latency. Six new tests
exercise missing display, additional delay, altered cadence, exclusions and
overlapping coverage. Earlier793 predates the final cross-report binding guards.

The full Python suite passes606 tests; `git diff --check` passes.

## Remaining work

Expand paired background coverage in room1; cover both directions and the NES
same-frame cases with store/input-to-render timing. Keep long encounter stops
visible and distinguish simulation workload from publication jitter. Then
qualify any promoted combination (including the separate noise correction)
before restarting Rival and capturing real Blackmagic audio/video.

Review, original/port collages, failure examples and playable emulator audio:
<http://127.0.0.1:8766/main-phase-review-795/>.
