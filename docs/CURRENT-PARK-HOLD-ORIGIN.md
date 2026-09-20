# Current park holds: repeated game commands, not missed renderer updates

[Every long hold, native screenshots/audio and exact stores](http://127.0.0.1:8766/current-park-holds-2273/)

No cartridge changes, Rival restart, controller input or OBS operations.
The offline candidate remains compact-pair2242,
`f7f8e725acaaef5592ededba9149ce17e1d7a43767a8deae739f825270c6c829`.
This investigation narrows current emulator scrolling concerns; it does not
clear the older unmatched physical hold, loading or audible popping.

## Fresh original-game control

NES normal2271 and combined main/renderer observer2272 use the identical
`rcr_raster_libretro.so` binary (SHA254b71d6f6e0). Both complete8,548 frames;
all frame images, full game RAM, input, PPU telemetry and PCM agree. Original
main-start F27D, input F282 and camera-store E2B1 opcodes are checked against
the source ROM. Main and actual pixel-shifter observations cover7000–9000,
including both complete park sweep phases.

First attempts2267/2268 omitted PPU telemetry. The dependent auditor refused
the missing field rather than inventing rendering-enabled state. Those
captures remain, but2271/2272 are the qualified replacements. No threshold
was changed. Historical report651 also has a changed-source binding and is
not reused as current evidence; its underlying pattern motivated this rerun.

Current SNES main2260/control2259 and renderer2256/control2246 independently
pass same-core full9,225-frame timeline/PCM equality. The main and renderer
episodes also agree with each other. Complete start/input/store/finish chains
are rederived from the bound raw sparse trace, with actual instruction bytes,
stack checks and native NMI advances.

## All long holds, not only equal-step endpoints

The earlier summary counted13 SNES14-frame holds with matching two-pixel
endpoint steps. The new auditor includes **every interval longer than four
frames**, including direction/speed changes and the long turn-around stop.

| Measurement | Original NES | Current SNES |
| --- | ---: | ---: |
| All long holds in the two sweeps | 18 | 19 |
| Duration histogram | 16×14,1×6,1×178 | 17×14,1×12,1×252 |
| Repeated-command explanation passes | 18 | 19 |
| Changed stores with covered display | 403 | 400 |
| Store→display | 400×next frame,3×same frame | 400×next frame |
| Changed target never displayed | 0 | 0 |

For every long hold, including both endpoint-producing stores, the audit
requires two-frame start/store spacing, repeated identical camera commands,
and the explicit next-frame hypothesis to match **every rendered frame**
through the interval. Current SNES additionally requires complete two-tick,
two-frame game loops. NES observation does not include F2DA completion and
therefore does not claim that additional completion proof.

A14-frame hold contains six repeated identical camera commits. The252-frame
SNES turn-around interval has125 repeats while complete main loops continue
at normal cadence. These are not unserviced new scroll positions or a frozen
main loop in this measured execution. The corresponding game-motion cause
(jump, collision, clamped camera, etc.) is **not** inferred from a raw state
byte. Inputs, player position, working/committed camera and original0300–0307
bytes are retained as context for later causal work.

Both systems execute the same phase-based controller policy but have different
encounters. Counts and turn-around durations are not paired causal comparisons
or a whole-game speed ratio. The NES counterexamples support the behavior
category, not event-for-event equivalence or a waiver of physical testing.

## Regression strength and auditability

Two derived negative controls target an otherwise explained hold: delay its
displayed endpoint by one frame, or remove one observed game update. Both
must change that same hold to unresolved. They are sensitivity tests on the
audit, not executed ROM faults.

Six unit tests cover complete repeated-command evidence, missed/slow updates,
late display, absent NES finish instrumentation, nonrepeating commands and
malformed timelines/ordering/derived intervals. Full suite:1,087 tests pass.
Each of37 long intervals has untouched frame panels and an unprocessed native
audio excerpt. All renderer series, stores, inputs, unresolved states and
source hashes are in report2273. No images are moved to manufacture a match.

## Effect on the work queue

Do not try to eliminate these measured stops by accelerating the original
game or changing its camera behavior. They do not reproduce a port-specific
renderer stall. Keep the older unmatched physical hold separate, requalify
the current candidate's menu/status and worst-case scheduling paths, and
prioritize the still-unclassified native audio transients before promotion.
