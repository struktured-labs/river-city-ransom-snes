# Full-route original-NES versus SNES camera latency

September 18, 2026. Review with 24 untouched source frames:
<http://127.0.0.1:8766/triangle-route-latency-review-1000/>.
Current game ROM `071c89e` is unchanged. No Rival input, restart, or OBS change.

## What the additional coverage changes

Original-NES capture 993 covers the entire 8,548-frame route, not just the
previous park window. The complete video/game/PPU timeline and WAV exactly
match independent normal capture 331. Report 994 checks 3,604 exact main-start,
input-call, and pre-`STA $F6` chains, retaining ten unpaired boundary/transition
events. These chains measure camera commit timing, not main-loop completion.

Report 995 joins those actual accumulator/high-bit camera values to every
eight-pixel fetch group on all 160 street scanlines: 32 groups per line.
Identical original-RAM stable-gameplay predicates cover 7,087 NES rendered
frames. Current SNES report 991 covers 7,211 frames, requalified after the
segment helper gained explicit NES/SNES rendering-enable selection.

Histogram notation below is `delay in frames: number of changed commits`.
“Start” is the observed game-loop start, not a physical button press.

| Room | NES store → display | SNES store → display | NES start → display | SNES start → display |
| --- | --- | --- | --- | --- |
| School street 0 | 0:1, 1:257 | 1:258 | 1:1, 2:257 | 2:258 |
| Alley 1 | 1:133 | 1:136 | 2:124, 3:9 | 2:136 |
| Mall 2 | 0:88, 1:58 | 1:146 | 1:88, 2:58 | 1:146 |
| Park 3 | 0:3, 1:417 | 1:390 | 1:3, 2:417 | 2:390 |

No missing displayed camera in either qualified sample: 957 NES changes and
930 SNES changes. The original has 92 same-frame store/display events; the
port has none. That alone is not evidence of extra game-loop latency. In the
mall, the port commits in its starting frame and displays next frame. NES
commits in the following frame, then displays either that frame or the next.
All 146 SNES mall changes therefore take one frame from loop start, versus
88 one-frame and 58 two-frame NES changes in the independent encounter.

The street and park each retain original same-frame exceptions. Nine alley
changes take three frames from main start on NES, versus two on the port's
sample. Different encounters, route lengths, and host-frame phases prevent
event-for-event speed or latency claims. No fitted lag or camera alignment is
used. This evidence does not certify physical input response or the whole game.

## Sensitivity and provenance

Report 999 injects two mutations into copies of the actual first qualified
SNES change in each room: one extra presentation frame and a missing target
camera. All eight are detected exactly. It neither edits source captures nor
passes these synthetic failures off as real gameplay observations.

The test suite now has **732 passing tests**. New tests cover NES rendering
enable state, rejected unknown systems, duplicated fetches, one-group splits,
invalid shifter sequences, mandatory PPU/RAM telemetry, inherited observer
configuration, exact one-frame mutation response, missing-camera detection,
and preservation of the original evidence during mutation tests.

Capture wrapper `capture_nes_route_store.py` binds its own implementation,
the capture tools, observer source, core, ROM, and normal receipt before
capture, then verifies those bindings afterward. It explicitly requests the
full-route exact-PC and pixel-fetch observers plus PPU, RAM, and image telemetry.
Legacy NES captures already contain full game RAM even when their optional
`full_ram_telemetry` flag is false; validation checks the actual 2,048 bytes.

Initial attempt 988 was stopped after detecting misnamed event variables.
Attempt 989 completed but omitted PPU-register telemetry; the neutrality
audit rejected it despite matching audio/video/game state. No report 990 was
published and neither attempt is used as qualified evidence. Capture 993
corrects both configuration omissions. Sources and raw captures were not
retroactively filled in from the baseline.

Page 1000 supersedes preliminary pages 996/997 and the narrower prior page
987 for current four-room conclusions. All 24 panels are original whole-frame
PNGs checked against both their file hashes and recorded decoded-video RGB
hashes. They show the first qualified change in each room/system, not matched
encounters or pixel-equivalent game states. The independent exact-background
comparison remains in report 979.

## Next action

Do not change the stable scheduler based only on the store-delay histogram:
the mall's earlier commit demonstrates why that would be misleading. The
existing same-frame RAM publication gate remains failed, not waived, and the
physical scrolling anomalies are not automatically cleared by emulator data.
The next priority is the unresolved physical combat audio gaps, with bounded
capture and evidence capable of distinguishing musical rests, synthesis, and
capture-path faults. Full-game endurance and physical input latency remain open.
