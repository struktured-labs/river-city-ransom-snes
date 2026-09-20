# Controlled school return: confirmed saving, newly isolated fade failure

[Same-state four-cartridge comparison](http://127.0.0.1:8766/combat-checkpoint-review-2137/)
· [First actual NES/SNES school return](http://127.0.0.1:8766/school-return-entry-2142/)

No cartridge was deployed and no Rival/OBS/controller state was changed.
Rival retains the splash-only57a046b683c4 build. Speed candidates remain offline.

## Why this test was needed

The full-route newer scheduling trial stopped reproducing a previous school
return. That missing encounter was not evidence of a fix. The new harness
replays identical saved CPU state, complete128KiB WRAM and controller inputs
through the parent, shift-only, scheduler-only and combined cartridges.

Checkpoint capture2120 saves after2555 and4174 during the unchanged4,916-frame
running-jumps policy on parent1947. Capturing the states leaves the complete
uninterrupted video, original game RAM, input timeline and PCM unchanged.
Fresh-process same-ROM controls2129/2130 then reproduce180 frames each exactly,
including each callback's native PCM bytes. All eight saved CPU registers
(PC/A/X/Y/S/P/DB/DP, including E in P) and complete WRAM match at restore.
No emulated boot frames run before restore.

The replay guard requires those exact current-source controls before cross-ROM
work. It regenerates the exact active-row patch and/or assembles the signed
shortcut from current source, checks all remaining ROM bytes and linked labels,
and rejects a checkpoint PC overlapping changed instructions. It does not
accept an arbitrary helper merely because a manifest was rehashed. Historical
instruction counters are disabled: these replays cannot be used as instruction
traces. Source/snapshot/artifact hashes and initial-state checks are retained.

Initial exploratory resumes2121–2128 were superseded after adding canonical
helper assembly to the guard; authoritative controls are2129/2130 and variants
2131–2136. Earlier files were not rewritten or regraded.

## Same-state results

The first observed room/off/on edges anchor the comparison. All40 fixed fade
offsets remain compared; no best-match image alignment or time-fitting.

| School return | Parent | Shift only | Scheduler only | Both |
| --- | ---: | ---: | ---: | ---: |
| Completion-to-completion interval | 26 | 23 | 26 | 23 |
| Room change→visible scenery | 33 | 30 | 33 | 30 |
| Rendering off→visible scenery | 33 | 30 | 33 | 30 |
| Rendering on→visible scenery | 9 | 9 | 9 | 9 |

Completion intervals here come from original052B counter changes observed at
frame ends, not exact-PC instruction timestamps. First/last partial intervals
are excluded explicitly; no interior change is discarded. Every school variant
retains its long26/23-frame interval. The three-frame improvement is now
confirmed from the same starting encounter, including with newer scheduling.

Alley entry remains20 frames from room/off edge to visible,7 from rendering
enable, with a15-frame completion interval in all four variants. Shift-only
alley replay matches all180 frames of video/game RAM/registers/native PCM;
the shortcut does not affect this particular window. Active/both produce later
state/audio timing differences, retained in their reports. No acoustic quality
claim is made from their waveforms.

All school/alley variants match their parent's40 relative fade offsets. This
**does not prove those parent fades match NES**, which is why a new reference
was needed. Cross-ROM reports intentionally do not assert same-ROM equality
or release readiness; their valid-comparison flag refers only to controlled
starting state, patch scope, input delivery and fault checks.

## New original-NES reference exposes remaining bug

`school_return_campaign.py` navigates school→alley→school using only preceding
frame game-state reads and ordinary pad inputs. Both systems use the same
policy and first-three-consecutive waypoint completion, without memory writes,
save states or system-specific input branches. Encounters may evolve differently.

Fresh complete captures: NES2140 has2,568 frames; SNES2141 has2,877. Whole-route
lengths include different boot/splash durations and are not gameplay speed ratios.
Two earlier2138/2139 runs failed metadata emission (dependency needed a Path,
not a string); they are retained, not accepted. Corrected runs are fresh.

Audit2142 selects the first actual1→0 room return, never the initial school
startup or a more favorable later return. Results:

| First return visibility | NES | SNES combined2087 |
| --- | ---: | ---: |
| Room change→visible | 34 | 29 |
| Rendering off→visible | 34 | 30 |
| Rendering on→visible | 7 | **9** |

**FAIL: fade publication is two frames late after rendering resumes.** All40
fixed offsets remain in the report; shorter total loading does not waive the
fade mismatch. The actual enable+7 images were inspected: NES has school
scenery; SNES is black. This test covers a return transition absent from the
previous three forward-entry checks.

## Next implementation target

Validation:1,050 unit tests pass (`/tmp/rcr-tests-2143.log`), including12 new
checkpoint/navigation/return-edge tests. Both review pages have169 current
source bindings and76 served artifacts verified against local hashes.

Trace the first post-return fade service and native hidden-row scheduling.
The state-controlled comparison shows the active15-row cap alone leaves the
school+9 timing unchanged. Investigate the inactive/state2 path and main/NMI
handoff rather than changing the original fade timer or concealing the delay
with a different alignment. Keep both whole-load and fixed-offset fade gates.
Any new candidate must retain forward entries, scrolling, menus, cadence and
audio checks before deployment. Physical pops and full original-speed parity
remain open.
