# Phase-aligned camera-boundary audio, experimental3919

Not promoted or deployed. Working parent3890 remains available unchanged.
Trial SHA256 `f46e04733e2a3ded0ec9ddff94fa8930d88394a4217e64a11dba38ed119d9141`.

## Mechanism and tests

Current trace3912 shows alternating early camera-boundary sound calls and normal
line80 interrupt calls. The slow8532 driver also executes17 fused sound commits,
versus4 at8530. Those updates are real work, not a redundant wait to delete.

The 29-byte helper in `snes/audio_boundary_wait80.asm` is installed in guarded
free padding7F40 in all eight runtime banks. It replaces only the existing
boundary JSR7885 with JSR7F40. After the original pending/depth/mapper/NMI-policy
and beam32..239 admission checks, it waits until80, rechecks the upper beam
limit, and tail-calls the unchanged service. Interrupts remain masked as they
already were at this boundary. No event/token is fabricated, and the normal
interrupt phase remains80. This spends CPU time waiting; speed is a tradeoff
to measure, not an assumed invariant.

Emitted-byte interpreter tests cover every beam32..261, at most49 synthetic
beam samples, late rejection, a wrong-phase mutant, guarded patch locations
and preservation of all other bytes. Combined with phase48 tests:5 pass0.069s.
These tests check control flow, not physical beam-clock timing.

## Audio improvement and remaining variation

Ordinary3920 and observed3921 complete9,090 frames with exact same-core primary
video/input/state/nativePCM equality. Native audio retains8,641 packets,
1,588 restart checks and4,846,034 stereo sample frames. No clipping. Peak6539,
maximum adjacent step4625: neither value proves a pop-free waveform.

| Stable packet gaps | Parent3890 | Trial3919 |
| --- | --- | --- |
| Minimum / maximum | 12.030 /20.921ms | 12.744 /20.036ms |
| 5th /95th percentile | 14.477 /18.861ms | 15.429 /17.615ms |
| Median | 16.636ms | 16.655ms |

Percentiles use sorted values at rounded `(n-1)*p` indices. Both arms retain
7,342 stable and1,298 excluded intervals. No exclusions changed to improve the
statistic. The longest trial gap is7108→7109, room2; audio jitter is reduced,
not eliminated. Native output is available in audit3922.

Neutral instruction replay3923 took25.521s. At8530–8533 all four original sound
driver entries now fall at line80. Return gaps are16.781/17.321/15.621ms,
versus13.902/20.201/13.721ms in3890. Original driver duration still varies.

## Tradeoffs that block promotion

All route game-counter/input/logical-camera trajectories match3890;52 rendered
pictures change and are retained. Read-only full-route-neutral observation3924
took32.844s and sampled84 text-window frames. Original nametable sources match
in all84. The strict comparison3925 fails:

- At5997 row25/column15, both sources/stages containE808; parent VRAM is current,
  but trial still has0008 and the row remains ready.
- At6003 row25/column18, both sources/stages containDA08; trial again still has0008.
- At6004 row25/column19, trial publishesE508 earlier than the parent.

Two-player combat3926 runs4,930 frames per policy, with full same-core neutral
observation and actual two-port input checks. Review3927 retains all busy and
excluded contexts. Running/jumping:1,709 two-frame intervals, no off-cadence
interval. Sustained attacks:1,751 two-frame intervals **and one three-frame
interval1797→1800**, no faults. Parent3890 had1,752 two-frame intervals. The
trial's affected camera commit occurs1799 line146/cycle820, game finish1800
line32/cycle1198. The speed gate fails; the good ordinary-route cadence cannot
override it. This is not matched original-NES encounter-speed proof.

Next: trace that exact combat boundary and the two queued text deadlines before
changing the wait strategy or publisher. Do not waive a frame of slowdown for
better packet timing, or claim this experimental build is ready for hardware.
DMA/renderer/palette/status checks on3890 do not qualify3919.

## Evidence

- [Native audio, every packet interval](http://127.0.0.1:8766/audio-boundary-wait80-audio-review-3922/)
- [All52 changed pictures and raw text tradeoffs](http://127.0.0.1:8766/audio-boundary-wait80-gallery-3928/)
- [Combat, including the failed interval](http://127.0.0.1:8766/audio-boundary-wait80-combat-review-3927/)

These links are workstation-local. Audio analysis took30.578s separately from
capture. No physical SNES/MiSTer, OBS changes, restart or release promotion.

## Deadline attribution, follow-up3933

Fresh combat control3929 and instruction observation3930 reproduce4,930 frames
with exact primary timeline/nativePCM and actual two-port input equality. The
parent trace3932 reuses its authenticated normal3904; its observation is also
fully neutral. They do not have equal encounters/iteration phases at every
same-numbered frame, so subtracting their instruction costs would not establish
an equal-work speedup or slowdown.

Trial3919 finishes one iteration at1797 line229/cycle1352 and starts the next at
230/1002. That iteration commits the camera1799 at146/820 and finishes1800 at
32/1198. The strict three-frame interval retains three native-NMI advances;
there is no missing-NMI evidence in this interval. This rules out simply
reapplying the previous lost-edge fix as its explanation. The fixed wait shifts
iteration phase and consumes real CPU capacity; it is not free just because
the ordinary route retains two-frame cadence.

Neutral ordinary instruction capture3931 (22.897s) covers5996–5997. At5996 the
camera enters36/150; sound starts80/836, returns101/626, and camera continuation
begins121/82. At the frame boundary the trial row is still dirty, not prepared.

[Attribution3933](http://127.0.0.1:8766/wait80-deadline-attribution-3933/) verifies
the exact source→prepared→VRAM sequence without aligning either arm:

| Text word | Source, both | Parent prepared /VRAM | Trial prepared /VRAM |
| --- | --- | --- | --- |
| row25/column15, tileE8 |5995|5996 /5997|5997 /5998|
| row25/column18, tileDA |6001|6002 /6003|6003 /6004|

Both stages start from the old value and reach the new value inside the captured
windows; these two generations are not censored. The preparation→VRAM delay is
one frame in both arms. Therefore these particular regressions originate in
preparation timing, not a longer wait for an already-ready row. This does not
prove correctness of every other producer/consumer generation.

Three unit tests distinguish preparation delay from ready-row publication
delay and reject source mismatches and censored generations. All pass. Existing
strict text and combat gates remain failed. Do not extend VBlank/DMA deadlines
to fix missing prepared data, and do not add another global phase guess.

Next mechanism to investigate: preserve the improved sound-delivery cadence
without making game/producer execution spend the early interval in a masked
busy wait. The native sound bridge itself has substantial handshake waiting;
any attempt to overlap or queue that work must first prove exact command/event
ownership and actual native-PCM behavior. No protocol change is implemented by
this diagnostic, and no acoustic-equivalence claim follows from it.
