# Pause audio scheduling: measured delay, rejected implementation

Working experimental3583 remains unchanged and is not newly deployed. The full
speed/scrolling/audio goal remains active. No MiSTer or OBS access occurred.

[Browser evidence](http://127.0.0.1:8766/pause-audio-investigation-3625/) contains
unaltered native pause clips, settings/status pictures, exact instruction events,
70 source bindings and the rejected experiments. The page was rendered and
visually inspected. This is not a verified audio fix or physical/pop-free verdict.

## What changed the diagnosis

The original NES pause-status replay167 produces its separated menu sound at
input offset57. Working3583 capture3607 and parent3527 capture3610 both produce
it at58. Existing onset audits3608/3611 remain FAIL; no threshold was relaxed.
The original and current game's `$003F` menu state reach `$A0` at offset57.

Fresh observer3612 preserves all2,535 full video/input/state timeline rows and
native PCM exactly. It observes frames1430–1440, including the menu-state store
at frame1435 line56, sound pointer setup at line58, and original sound wrapper
`C1:FA54` at line256. The pointer-store → driver-entry interval is270,794 captured
master clocks. Source APU writes for native event1046 begin at1435 line261 and
continue into1436 line4. Thus the initial hypothesis—driver executes before the
new cue—is contradicted. Late service/cross-frame delivery is directly observed.
This still does not establish the cause of every physical pop or NES waveform
equivalence. Original NES instruction-level cue/driver timing is not yet paired.

Present Status opening/reopening in working3583 still passes the original digit,
RAM-value and fixed-region pixel oracle (3609 and revalidated review3625).

## Rejected variants, not promoted

- 3613 moves pause-only early audio before the native publisher using a helper
  at7500. This is wrong because the native NMI calls with PB00, where that
  address is not cartridge ROM. Capture3614 terminates with an invalid-callback
  error; no complete receipt exists. Its cartridge and partial images remain.
- 3617 moves the same helper into bank00-visible ROM atD900. Capture3618 fails
  settings loading:2,940 frames, incomplete, wait-settings deadline reached.
- 3621 additionally preserves incoming A/P at the publisher boundary. Capture3622
  has the same boot failure. Observed3623 reproduces its entire finite2,940-frame
  timeline and native PCM exactly, including the failure. Eleven inspected NMI
  calls at535–545 take the no-audio branch and restore A/return-stack state.
  Executed helper tests independently check A/P and eligibility/token behavior.

Neither mapped trial reaches the requested pause scene; neither can demonstrate
an audio improvement. The failing no-service boot window rules out newly
executed pause sound service as its immediate cause. The underlying timing
dependency remains unresolved; do not paper over it with another arbitrary
deadline or delay. Inspect source/stage/commit behavior across this transition.

No source-bound historical tool was modified to make the experiments pass.
The new helper tests execute assembled bytes against an independent eligibility
oracle, reject the real unmapped-target shape, expose the old helper's A/P
clobber, and restrict mutations to helper/checksum bytes. The suite passes
1,424 tests in20.510s (`/tmp/rcr-tests-3624.log`); this does **not** qualify the
failed cartridges. Neutral pause capture3612 took6.227s, excluding verification.

## Next useful work

Trace the newly exposed settings publication timing dependency with the working
and rejected builds before moving sound across that boundary. Then require an
actual improved pause onset, unchanged sound-event count/cadence, complete boot,
status/other menus, DMA/CHR/OAM/scrolling checks and physical audio acceptance.
Do not exchange audio latency for missing graphics or silently skip driver ticks.
