# Park coverage: verified route, retained endurance and image failures

Candidate unchanged: `build/pending-palette-queue-327/native-cpu.sfc`, SHA-256
`4339df2e5613e0d5af4ec7aa7e3888b991311281988b75a838f992e9e6d3a958`.
No ROM edits, hardware deployment, restart, or new physical audio claim.

## Why the old route was insufficient

The original fixed `traversal-park-stress` replay remains unchanged. In the
latest capture (`pending-palette-queue-normal-328`), `park_02_right_run.png`
shows “ALEX has lost all of his power”. Room changes from 3 to 2 during the
scheduled pause input at frame 8109. Subsequent scheduled “park” movement
runs in the mall pause menu: `park_03_right_run.png` confirms it visually.
That explains the 21 common park camera positions; completion of that
fixed input schedule was never sufficient evidence of full park coverage.

## New first-class harness

`tools/park_waypoints.py` uses only preceding-frame original 2-KiB game RAM.
It waits for unguarded, unpaused gameplay with a completed original fade.
It enters room 3 from the mall, then navigates between inner world-coordinate
targets x >= 650 and x <= 224 using the original two-button jump and D-pad.
There are no emulator writes, saves, cheats, forced enemy states, death
recovery, or system-dependent choices. Each waypoint has a 1,920-frame cap
and must stop at its first three consecutive matching observations.

The four-cycle scenario `traversal-park-coverage` is frozen separately from
`traversal-park-single-sweep`, which completes one outward-and-return lap.
The shorter scenario is a targeted scenery-coverage test, not an endurance
replacement. Both are fresh full boot-to-end captures, not truncated or
relabeled pieces of the failed longer run.

The original café waypoint module and hashes remain unchanged. The capture
and verifier select and hash the applicable policy. Verification recomputes
every delivered input from the preceding RAM, checks complete frame/PCM
coverage, and validates first stable completion or the full timeout.
Rehashed wrong-input, false-completion, and wrong-policy mutations are rejected.

## Executed results

| Evidence | Result |
| --- | --- |
| `park-endurance-audit-331` | **FAIL**: NES completes 12,336 frames; SNES times out at 10,866 during second east sweep after death/return to room 2. Normal-core replay has identical full timeline and PCM. |
| `park-single-route-332` | Both finish: NES 8,548 frames, SNES 8,946. Full SNES observer/normal timeline and PCM identical; no native faults or stable unpaused park packet gaps > 536,049 clocks. |
| `park-single-scroll-332` | **FAIL image gate**, coverage PASS: 748 common positions (rooms 0/1/2/3: 259/83/110/296), unchanged minimum 64 each. No late publications; second-stable samples no later. |
| `park-single-audio-332` | 8,789 ordered acknowledged packets cover every completed NMI, no unfinished tail or unflushed CPU writes. Full WAV and gap review clips retained. Not a perceptual click detector. |

The 15 differing park scenery bands are at camera 142..170, even positions.
Inspection of the paired images shows the jumping player entering the fixed
y=32..79 strip (for camera 160 the differing box is x=183..198, y=66..79).
The original comparison at that camera has the player elsewhere. The band
was not narrowed, dynamically masked, aligned, or replaced by a later image;
all 15 failures remain visible. These are not evidence by themselves of
incorrect scenery, but the unchanged image gate cannot certify that region
on these samples. A future test must separate background publication from
sprite occupancy with independently validated evidence.

The state-adaptive routes have independently evolving inputs and enemy
states. Their duration difference is **not** a same-input gameplay speed
ratio. In particular, the NES finishing the endurance run while SNES dies
needs encounter investigation, not an assumption that the cause is slowdown.
The old strict room-entry failures remain: 9/7/9 versus NES 7/7/7 first
scenery; room 2's forty fade checkpoints pass, rooms 1/3 do not.

## Tests and next work

420 Python tests pass. New controls exercise waypoint bounds, loading,
pause, wrong-room rejection, read-only inputs, first stable completion,
full timeout, immutable historical prefix/policy, rehashed capture mutations,
and audit rejection of timeout/fault/non-neutral/absent-park/late-packet cases.
The historical `waypoint-shop-repeat-nes-196` (7,666 frames) and
`waypoint-shop-repeat-snes-196` (7,678 frames) also reverify completely with
the new dispatcher. All 98 main review links and every linked asset in the
four new report pages return HTTP 200. `git diff --check` is clean.

Private web collages and full audio are linked from
`http://127.0.0.1:8766/oam-word-review-208/`. No ROM downloads are enabled.
Next: independently validate background-only scrolling evidence despite
jumping actors, investigate the longer encounter divergence, then resume
rooms 1/3 timing and full audio-fidelity qualification before any deployment.
