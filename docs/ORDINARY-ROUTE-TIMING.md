# Current audio trial: four-room cadence and original NES sound timing

Candidate3065 is unchanged:
`964ef6c71257b89c1f9097ca6b4e2f9418b530057d5235e83f5e85c8ebd6711c`.
No hardware deployment, controller input, reset or OBS operation was performed
in this pass. Rivalmage remains off-limits; Bluemage capture routing is still
unconfirmed. These are emulator measurements, not physical audio acceptance.

[Timing tables and bound raw records](http://127.0.0.1:8766/ordinary-route-timing-3101/)
and [original-NES school-return collage](http://127.0.0.1:8766/ordinary-early-audio-school-audit-3099/).

## Four-room speed regression

Fresh SNES sparse-PC capture3097 and same-core unobserved control3100 each
execute9,248 frames. Every input, full original RAM snapshot, video frame and
native PCM sample agrees. Exact linked start/input/camera/finish PCs, opcode
preimages, stack restoration and native NMI counts are checked.

NES capture3098 adds original sound-wrapper entry/return observations to the
main/input/finish PCs. It exactly reproduces same-core control977 across all
8,548 frames, including native PCM. Its26,610 events pass point, timestamp,
register, frame and coverage validation. Different total route lengths must
not be used as an FPS ratio: these are independent encounters.

| Room ID | NES consecutive intervals | NES frame gaps | SNES consecutive intervals | SNES frame gaps |
| --- | ---: | --- | ---: | --- |
|0|594|593 ×2,1 ×3|601|601 ×2|
|1|1,741|1,729 ×2,12 ×3|1,745|1,745 ×2|
|2|470|470 ×2|478|478 ×2|
|3|728|728 ×2|926|926 ×2|

All3,750 selected SNES intervals have two frames between starts and exactly
two native NMI advances. The original NES has13 three-tick iterations in this
independent run. This does not establish equivalent enemy work or whole-game
speed parity, nor does it waive renderer/publication checks.

The selector considers consecutive loops **before** applying room, task,
pause, fade and transition exclusions. All excluded and censored records are
retained. Original NMI-busy `$0107 bit7` is not excluded; this particular stable
route population contains no sampled busy flag. A synthetic busy three-frame
loop is explicitly caught by the tests, not filtered away. Existing two-player
busy-inclusive regression coverage remains separate.

## Original sound-wrapper baseline

There are7,898 complete original `$FA54`→`$FA64` calls, with matching stacks.
Within the same stable-room predicate, all7,087 consecutive selected driver
entries are one frame apart:

| NES CPU-cycle interval | Minimum | Median | Maximum | Standard deviation |
| --- | ---: | ---: | ---: | ---: |
|Wrapper entry→next entry|29,775|29,781|29,786|1.6853|
|Wrapper return→next return|26,637|29,788|34,599|793.6043|

For every pair, return interval equals entry interval plus the change in driver
duration, exactly. This demonstrates that the original game itself has variable
driver completion timing despite regular entry timing. It does **not** identify
audible pops, measure individual APU-register writes, equate driver return with
DAC output, or establish permissible SNES jitter. NES CPU cycles, SNES master
clocks and SPC ticks are not mixed or aligned by fitting.

The prior71.36% reduction in SNES completion-interval standard deviation remains
the separate fixed-population parent3032 versus trial3065 measurement. The new
NES baseline is context for further per-write/synthesis investigation, not a
claim that remaining SNES sound differences are inherited or acceptable.

## First actual school return

Capture3096 executes the complete school→alley→school policy for2,877 SNES
frames. Audit3099 compares the first actual alley-to-school return to original
NES capture2140; startup cannot substitute for a return.

All40 fixed background offsets match exactly. First visible background is at
render-enable+7 on both. Room-change/render-off to visible is29 frames on SNES
and34 on NES. All four gates pass. The collage intentionally shows independently
positioned characters; the equality oracle is the fixed background region, not
the whole frame or matched encounters.

## Verification and next work

Five new tests cover busy retention, genuine pause exclusion, unhidden slow
loops, avoiding artificial gaps across excluded spans, exact sound-duration
decomposition, and malformed/reentered/stack-corrupt sound pairs. Full suite:
**1,262 tests pass**; `git diff --check` passes. Both published pages were opened
and visually inspected. Reports retain hashes for their source dependencies,
captures, traces and published artifacts.

Remaining work includes per-register NES/SNES timing and sound-fidelity checks,
broader gameplay coverage, and physical audio/video self-verification through a
confirmed Bluemage capture path. No pop-free or release-ready verdict.
