# Physical park scrolling and audio

Follow-up: [exact-frame hold analysis](CAMERA-HOLD-ORIGIN.md) distinguishes an
original-NES repeated-command hold from missing main work, and publishes the
two Rival event collages. Physical causes remain unresolved;652 tests pass.

Current ROM `840de24` was exercised on Rival without another restart. The
remote file hash and MiSTer PID1258 launcher arguments still match deployment818.
This is file/process evidence, not cartridge-RAM readback.

Ordinary bounded USB input reached the mall through the alley, then the U.S.
Mail park. A16-second back-and-forth sweep survived. A subsequent24-second
combat request died about halfway through; the recording shows the loss-of-
power message, mall respawn and remaining leftward input returning to Trash
Pick-Up. The latter is not a successful long park endurance run.

SNAC was temporarily No for USB injection, then visually restored to **Yes**.
Final859 screenshot shows the game paused by Trash Pick-Up with OSD closed.
Saved SNES.CFG remains `066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
No physical SNAC-button test, OBS setting mutation or screenshot deletion.
MiSTer screenshot-saved overlays occurred during input; those side effects
are retained in the evidence rather than hidden.

## Recorded media

Read-only extraction of the continuing Blackmage recording produced:

| Segment | Recording interval | Video | PCM |
| --- | --- | --- | --- |
| Park sweep856 | 64711–64731s | 20s /1,200 frames | Stereo48kHz PCM16 |
| Combat/death857 | 64816–64842s | 26s /1,560 frames | Stereo48kHz PCM16 |

Both include lead/tail context, not only active gameplay. H.264/AAC browser
videos were re-encoded from the same requested intervals as the separate
decoded WAVs. Controller wall-clock requests are not calibrated acceptance
timestamps. Whole-recording metadata reports video start0.021s, audio start0;
that alone does not calibrate the rest of the capture pipeline.

Audio reports860 retain every exact-zero interval≥10ms plus playable strongest
sample-step events. Sweep peak2,300/RMS449.18/max-step1,183; second pass
peak2,495/RMS423.02/max-step1,019. Neither clips. Pause/death/transition silence
and shorter unclassified gaps are retained. This is not a pop-free verdict.

## Physical scenery measurement

`audit_physical_camera.py` decodes every video frame without frame-rate
conversion. The explicit skyline ROI is x340/y160/w1280/h120; five recorded
horizontal pixels correspond to one logical pixel. It searches displacements
within±4 logical pixels, requires spatial variation≥10, mean RGB error≤8 and
next-best margin≥1. It retains all rejected pairs and long stops.

Report862 accepts1,189 of1,199 pairs. Equal signed movement steps produce95
two-frame holds, two four-frame holds (one-pixel camera steps), and8/13/14/14-
frame stops. Ten ambiguous pairs remain. No1/3-frame interval occurs among
the accepted equal-step joins. The four-frame intervals are not waived.

This measures encoded scenery, not actual NMI entries or full-frame content.
OBS60Hz and hardware scanout are different clocks. Direction changes, collisions,
camera easing and capture duplication complicate interpreting a hold as a
speed defect. A fixed synthetic two-frame scrolling sequence using the same
scenery is recovered; injecting a duplicate creates a detected three-frame
hold. Unit tests also reject flat/unrelated images and missing frame pairs.

## Harness corrections and limits

An initial direct-script invocation of `run_mister_keys.py` failed before
hardware access because of package-only imports. Both script and module
invocations now work and have read-only help tests. The wrapper now snapshots
its source-file hash before starting the remote sequence. Episode853's prior
end-of-call hash overlapped that local import edit and is not a loaded-code
attestation; the unchanged remote helper hash and actual input receipt remain.
Episodes854/855 use the corrected early snapshot. A mock source-change test
protects this behavior without contacting hardware.

646 Python tests and `git diff --check` pass. No ROM, game graphics, controller
mapping or sound-engine code changed. Next: correlate the two four-frame
physical camera intervals with game/capture timing and improve surviving
combat coverage; keep audio onset/offset fidelity and full-game scope open.

Review: <http://127.0.0.1:8766/main-phase-physical-park-review-864/>.
