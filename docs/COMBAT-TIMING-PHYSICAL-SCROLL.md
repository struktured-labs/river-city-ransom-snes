# Combat timing and actual Rival scrolling

Follow-up: [matched jumping and exact physical-hold context](JUMP-SCROLL-REFERENCE.md)
narrows the camera observations below without declaring the hardware issue fixed.

September18, 2026. No game ROM changes in this iteration. Current game remains
`0956bd97b78f`. [Video, original capture frames and native audio](http://127.0.0.1:8766/combat-scroll-review-1315/).

## Combat regression

`capture_combat_loops.py` records exact main-start/input/finish sites on both
systems, plus the SNES pre-store camera site. Fresh captures1292/1293 exactly
match their independent normal captures1224/1226, including complete audio and
frame/RAM timelines. `audit_combat_loops.py` verifies the instruction identity,
trace ordering, caller stack and paired complete iterations before measuring.

Each system has701 complete loops in the seven explicit combat/pause/resume
phases: approach30, take-hits360, counterattack120, pause-request6,
pause-wait90, resume-request6, resume-wait89. All use two game ticks and all
consecutive starts within each phase are two physical emulator frames apart.
Unlike the older stable-room predicate, this check does not exclude paused or
hit states. A final incomplete iteration remains censored. Three mutations
of derived observations per system detect a third tick, extra physical frame
and missing complete loop; these are not executed-ROM mutations.

One SNES loop outside these phases takes three ticks: frames1192–1195 during
street loading, native transition-state2 with pending CHR work. It remains
explicit in `other_off_cadence`; no claim that every loading loop matches NES.
Independent encounters, rather than identical enemy/RNG states, mean this is
not equal-work whole-game speed certification.

## Audio hypothesis narrowed

Inspection of every completed packet in the focused encounter and the full
four-room route finds only constant-volume mode in enabled pulse/noise channels:

| Capture | Pulse1 | Pulse2 | Noise | Envelope-mode packets |
| --- | ---: | ---: | ---: | ---: |
| Focused1225 | 2,153 | 2,144 | 1,961 | 0 |
| Four-room1172 | 8,013 | 8,019 | 8,019 | 0 |

The legacy envelope16 sentinel therefore cannot explain these sampled pops.
The NES envelope definition is documented by
[NESdev](https://www.nesdev.org/wiki/APU_Envelope); no envelope patch is justified
as a fix for this observed stream. Short clicks and exact mixed-channel fidelity
remain open; the prior replay1291 only checks broader activity.

## Physical movement trial

Read-only preflight1295 verified the same running cartridge, idle OBS recording
and replay, and unchanged audio routing. SNAC was temporarily switched off for
the exact-identity initially-idle USB pad. Ordinary Start/B inputs chose1P,
entered the street and paused;1304 shows the starting scene.

`capture_mister_scroll.py` reuses the existing bounded dual-recorder handshake,
cleanup and pad validation with an explicit traversal input policy. Trial1305
records30 seconds, containing the complete22.7-second requested sequence:
unpause,16 seconds right with repeated A,4 seconds left with repeated A, pause.
No RAM edits, core replacement, saved configuration writes or unrelated OBS
changes. The requested A is not assumed to be proof of every jump's consumption.

Original recording:
`/home/struktured/Videos/drmario_sessions/20260918_114724_struktured_v6c_part2.mkv`.
1311 is a video/audio stream-copy MP4, and its AAC WAV is an exact float32 decode.

Camera audit1312 uses the predeclared scenery ROI(340,160,1280,120), scaled to
256 logical horizontal pixels. It accepts1,782 of1,790 pairs, retaining all
eight rejected pairs. Nonzero measured steps:88×2 pixels,26×1,1×3. Hold lengths:
47×2 frames,3×18,1×1,1×12,3×26,1×4. Unlike the earlier stationary combat recording,
this demonstrates actual scenery movement. Synthetic shift and inserted-duplicate
controls validate matcher sensitivity, not hardware timing.

Two short irregular observations remain:660→661(one frame),1063→1067(four).
Five exact decoded pictures in1314 show these intervals. Within the four-frame
camera hold the enemy position changes, so it is not a frozen whole picture.
It could still be gameplay movement, publication timing or capture behavior;
no original-NES equivalence or smoothness waiver is claimed. Long stops and
all rejected matches remain available in the report.

Audio audit1313 verifies the full input episode lies inside the recording.
Raw/AAC offset271,048 samples is trained only on seconds4–7 (correlation0.962).
Held-out correlations0.494–0.726 are insufficient for sample-exact attribution.
The214.7ms AAC gap at23.125s corresponds approximately to a256.0ms raw gap,
after the pause request at22.533s. Final AAC silence extends beyond the
raw branch's overlap and is not called physically cross-verified. Dead-monitor
and injected100ms AAC-only-cut controls pass. Pop-free output remains unproved.

## Handoff and next

1308 visually verifies SNAC Yes again;1310 shows OSD closed and the game paused
on school street at the newly scrolled position. Saved SNES.CFG remains
`066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
Owned OBS recording stopped, debug tap removed, adapter links/properties and
input audio routing unchanged.

Next isolate the two physical camera irregularities using actual pixel/capture
timing and compare short transients rather than treating broad RMS agreement
as a click-free gate. No new gameplay/splash/controller-mode fix is claimed.
