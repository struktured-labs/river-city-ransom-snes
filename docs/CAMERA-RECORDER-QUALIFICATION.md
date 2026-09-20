# Camera recorder: offline rejection, not a gameplay fix

The physical four-frame camera hold in `compact-game-camera-2413` remains
unexplained. A cartridge-side camera recorder must not change the timing it
is intended to measure. The historical offline results below were followed by
the bounded hardware trials described next. The physical comparison does not
explain the previous production hold.

## Extended-window physical trial (2026-09-19, 06:45 UTC)

[Video, fixed-frame collage and telemetry2594](http://127.0.0.1:8766/late-camera-hardware-review-2594/)
records temporary deployment2557 of diagnostic2547. Both screen guards2574
passed; the 22.7-second input episode2573 is bracketed by its 30-second recording.
Startup input2563 did not reach the intended paused state. Read-only observation
and a separate Start request established the actual paused reference2572:
school street, nearby enemies, approximately seven health bars. This is not an
identical encounter or starting state to the earlier physical run. The collage
retains a transient save-state notification visible at decoded frame300;
no frames or rejected scenery pairs have been removed to hide it.

Explicit saves2571/2579 bracket **493** new samples, sequences1301–1793.
Paused resave2585 is byte-identical. Auditor2589 verifies the unchanged earlier
prefix and all decoded records. Of435 consecutive two-NMI same-room pairs,
**61 change the working camera and53 change its display shadow**; all satisfy
the preceding-commit/current-shadow relation. Working and committed cameras
agree throughout; no interrupted sample or nonzero fallback is observed.
There are still57 unsampled intervals, maximum22 NMIs. The served counter
advances618 times over1,236 NMIs, which does not prove intra-gap cadence.
This is improved coverage, not proof that the hardware PPU always showed the
correct camera. No video/NMI alignment or interpolation was fitted.

Video2583 contains1,792 decoded frames,1,781 accepted scenery pairs and ten
retained rejected pairs. Equal-step holds:68 two-frame, one12-frame and
eight18-frame intervals; no four-frame interval. The production four-frame
hold remains unresolved. Diagnostic audio is deliberately not certified.

Production2367 was restored by receipt2586; the running launcher and unchanged
saved SNES.CFG were checked. Screenshot2588 verifies SNAC Yes, and2592 shows
the OSD closed at the1P/2P menu. OBS recording/replay are stopped, capture
cleanup passed, and audio routing is unchanged. This is a cartridge restart,
not restoration of the previous gameplay state.

1,149 unit tests pass (`/tmp/rcr-tests-2590.log`). Review2594 has49 verified
source bindings and18 verified artifacts, and was inspected in Chromium.
The review builder now validates either actual boot or reload receipts, with
tests rejecting conflicting saved-configuration identities. Historical2546
is retained but its builder source has since evolved;2594 is the fresh binding.

## Extended window: offline coverage improvement (2026-09-19)

Candidate `build/late-camera-logger-2547`, SHA
`607c106714faba68ef756da759c1066ec735ad97a90615c9897d1db7f3b8d5ef`,
changes only nine admission operands (eight replicated wait helpers and one
native wrapper) from cutoff194 to230, plus the checksum. It was not deployed
during this offline study; the subsequent bounded physical trial is above.
Its builder rejects wrong/ambiguous preimages and unrelated cartridge changes.

[Coverage, scanline comparison and retained picture differences](http://127.0.0.1:8766/late-camera-review-2552/)
show the same9,225-frame route, identical inputs/phase boundaries and all five
camera/tick/fallback frame-end fields. The actual renderer observer reproduces
its plain counterpart's full timeline and PCM exactly. Across7,618 eligible
active-game frames, all160 required scanlines match production. However,
two renderer coordinates differ outside that selection: frame2427/line53 is
an extra BG-disabled event, and frame6669/line61 changes main-screen17 to0
(BG1 enabled in the baseline). That transition difference is not excused by
the active-game result. The late recorder changes48 complete-picture frames
(versus15 with the early recorder), and both diagnostics change native PCM.
Neither is a timing-neutral gameplay release or an audio-fidelity observer.

Coverage improves from1,793 to3,495 records, and from208 to691 consecutive
two-NMI, same-room sample pairs with a nonzero working-camera change. Gaps
fall from405 to142, but the longest remains398 NMIs across this gated route.
No interrupted record is observed. This specifically improves the moving
camera coverage that was poor in physical trial2520; it does not attribute
the previous production four-frame hold.

Expanded fixture2548 passes168 ordinary cases and rejects all four mutants.
Control2549 requalifies the previous194 cutoff with the same expanded matrix.
Both include all16 bank rollovers and low-word counter carry at the last
admitted scanline, HDMA on/off and the earlier context/register cases. The
230-cutoff variant records through observed line229; maximum masked duration
is5,938 master clocks, and all ordinary tick interrupts arrive at line240/241.
The fixture still uses a minimal interrupt handler, not arbitrary full-game
interrupt workloads. Historical2457 is retained; the checker source evolved,
so2548/2549 are the current-source qualifications, not a retroactive rewrite.

The seed-staging gate now requires the full168-case matrix, the exact
candidate cutoff and all four distinct rejected mutants; false-green summary,
missing-case and duplicate-mutant tests reject bad proofs. No seed was staged
and no hardware input or restart occurred during this offline study. Rival's
regular2367 launcher and unchanged saved configuration were checked again.
1,147 unit tests pass (`/tmp/rcr-tests-2554.log`),201 review source bindings and
13 artifacts verified, and the rendered review was visually inspected.

## Physical comparison and coverage limit (2026-09-19, 06:21 UTC)

[Video, fixed-frame collage and every sample](http://127.0.0.1:8766/camera-hardware-review-2546/)
records the successful guarded traversal2520. Both guards2521 compare the
manually checked paused/OSD-closed reference2519 exactly. The22.7-second
controller sequence is bracketed by the30-second recording. Cleanup was
checked: the immediate observation2522 still showed recording active while
OBS finished stopping; follow-up2523 and final2540 confirm it stopped. No
restart of the recorder was made on that transient observation.

Explicit paused saves2518/2531 bracket265 new camera records (sequences56–320).
Paused resave2535 is byte-identical to2531. New auditor2541 validates the
unchanged prefix and exact resave, retains all records, and never interpolates
gaps. All226 same-room two-NMI neighbor pairs have the display shadow equal to
the preceding committed camera. Working and committed values agree in all265
samples; no interrupted sample or nonzero fallback counter is observed. The
served counter increases618 times across1,236 NMI ticks, including intervals
with sparse records. **Aggregate counters do not prove intra-gap cadence.**

Crucially, only **three** covered neighbor pairs change the working camera,
and only **two** change the display shadow. The38 telemetry gaps include a
214-NMI interval. This early-cutoff recorder mostly covers stationary periods;
its apparent success cannot qualify scrolling workload timing. Next recorder
work must improve coverage of actual camera changes while requalifying the
interrupt deadline and emulator camera behavior, before another deployment.

The video contains1,792 decoded frames,1,785 accepted scenery pairs and six
retained rejected pairs. Equal-step hold intervals comprise62 two-frame and
nine18-frame intervals; no1/3/4-frame interval is observed. This did **not**
reproduce or resolve the earlier production four-frame hold. No video/NMI
alignment was fitted. This diagnostic changes audio and some sprite timing,
so this run does not qualify gameplay sound.

Normal2367 was restored (receipt2536), running launcher and unchanged saved
SNES configuration checked, SNAC Yes visually verified2538, and the OSD closed
at the1P/2P menu2540. OBS audio settings remain unchanged.1,142 unit tests pass
(`/tmp/rcr-tests-2544.log`), including four new bracket/order/gap/stale-shadow
tests. Reviews2543/2545 are retained drafts;2546 supersedes them with explicit
moving-camera coverage and data-derived summary text.

## Boundary qualification and interrupted hardware trial (2026-09-19)

Executable fixture2457 passes134 ordinary boundary cases and rejects all four
mutants (late admission, native-mode interrupt, wrong SRAM wrap, wrong commit).
It executes the actual2440 wait/logger bytes with HDMA on/off, scanline and
delay variations, all16 SRAM bank wraps, and low-word counter carry. The
maximum observed masked interval is5,938 master clocks. This is a bounded
fixture, not a full-game worst-case interrupt proof. Unit checkpoint2459 has
1,138 passing tests.

Diagnostic2440 was temporarily booted on Rival (receipt2461) after staging
the unique seeded save2460. Paused export2483 contains29 valid records,
establishing seed loading and physical SRAM writes. The traversal attempt
was rejected by screen guard2487 before recording or controller input; its
reference mistakenly included the OSD. No traversal/camera-causality result
is claimed. The corrected paused reference2489 was not used for a new run.

The splash-audition handoff restored normal combined2367 using receipt
`build/sub-wub-restore-2490.json`; the running launcher was separately checked.
This restarts the cartridge, not the prior gameplay state. Diagnostic files
and failed guard evidence remain available; the camera hold remains open.

## Historical offline checkpoint2451

## Follow-up: actual branch repair and scoped camera observation

Fresh instruction-core control2434/trace2435 reproduce the same incomplete
3,195-frame execution and native PCM exactly. The first erroneous branch is
now observed, not inferred: at frame1193/line164, `$C0:E00C` executes `BCC $80`
and lands at `$C0:DF8E`, unused `$FF` padding. The earlier builder changed the
branch displacement byte instead of its opcode. Repaired2436 changes precisely
`90 80` to `80 04` (unconditional branch to `$E012`), plus the checksum.
The historical broken builder and artifacts remain intact; dedicated repair
tests reject a changed preimage, repeat patching and a wrong branch target.

Status capture2437 completes2,537 frames with139 samples and no faults, all
pictures matching the ordinary2367 control. PCM still differs. The longer
idle-route2438 fails to reach the park; it is not a usable timing probe.

Wait-loop2440 restores the original FAB8 call and instead enters from the
original two-tick busy wait. It admits recording only during early scanout,
with no pending/deferred interrupt context. It disables NMI before switching
to native mode and restores the non-raster policy after returning to emulation
mode. The scanline194 cutoff is still an empirical bound, not a worst-case
interrupt proof or permission to deploy.

Wait-route2441 completes9,225 frames against fresh production control2439:
all input/phase boundaries and five camera/tick/fallback fields match. There
are1,793 samples, no faults and no changed NMI counter inside a sample.
**Full neutrality fails:**15 picture frames differ and native PCM differs.
Wait-status2442 completes but also differs in picture/audio observations.
[Comparison collages and native PCM](http://127.0.0.1:8766/camera-wait-review-2444/)
retain every difference and the failed earlier route.12,718 source bindings
and23 served artifacts were verified; the rendered page was inspected.

Actual renderer captures2445/2446 each reproduce their respective ordinary
core's entire timeline and PCM. All9,225 frames are retained. The raw
position-by-position comparison2448 fails: one extra row shifts the sequence,
yielding1,077,654 positional differences. This preliminary report remains;
those are **not**1,077,654 independent camera errors.

[Frame/scanline-keyed audit2450](http://127.0.0.1:8766/camera-log-coordinate-review-2450/)
finds exactly one differing coordinate: frame2427/line53 exists only in the
diagnostic stream, with main-screen0 (BG1 disabled). No time alignment or
resampling is used. Baseline has1,447,459 renderer rows; diagnostic1,447,460.
The existing eligibility rule selects7,618 consecutive active-game frames;
all160 required lines in each are present and identical in both captures.
Missing/duplicate-line and one-pixel-scroll mutants fail the new unit checks.

This qualifies only camera observation for this tested emulator route, not
general probe neutrality, physical four-frame-hold attribution, sprite timing,
audio fidelity or full original-game speed. Before a physical diagnostic run,
the admission/interrupt boundary and recording coverage still need executable
qualification. At checkpoint2451, production2367 on Rival had not been changed
or restarted; the later startup trial above supersedes that deployment state.

Checkpoint2451:1,135 unit tests pass (`/tmp/rcr-tests-2451.log`), with a clean
`git diff --check`. Audit2450's12,737 source bindings, served report and HTML
were hash-verified, and its browser page was visually inspected. Passing unit
tests do not override the retained incomplete replay or neutrality failures.

## Same-core controls

The unchanged combined2367 cartridge was replayed as control2425. Diagnostic
2423 records original working/committed camera state, port display state and
interrupt counters into explicitly seeded SRAM; capture2424 decoded301 records.
Zero timeouts and zero interrupted samples are not a neutrality certificate.

| Capture | Executed diagnostic | Frames | Exact control timeline and PCM |
| --- | --- | ---: | --- |
| 2425 | None | 2537 | Baseline |
| 2427 | SRAM mapping only; recorder unreachable | 2537 | Yes |
| 2429 | Wrapper and gates, record writes skipped | 2536 | No |
| 2424 | Wrapper, gates and record writes | 2536 | No |

Both executing variants first differ in original RAM at335, audio at480,
picture at567 and scenario phase at1259. Gate-only and full-record variants
have identical phase and video observations, but their RAM and audio differ
from each other starting at1209 and1291 respectively. No startup frames,
stack bytes or audio samples were excluded to manufacture neutrality.

[Preliminary comparison collage and native audio](http://127.0.0.1:8766/camera-log-review-2430/)
retains the failures. Its flat source bindings do not constitute recursive
qualification of every inherited build manifest. This is rejection evidence,
not a validated physical camera diagnosis or release qualification.

## Idle-time alternative also rejected

Trial2431 restores the production audio call and moves the recorder to the
original main-loop wait, after the final FAB8 call. Capture2432 does not
complete:3,195 frames, stuck waiting for the street, no recorded samples,
adapter faults starting at1201. It must not be deployed. The native/emulation
interrupt boundary and original caller stack contract need investigation;
neither has been established as the cause yet.

The production cartridge remains combined2367, including the55 Hz splash tail.
These experiments make no claim to fix slowdown, scrolling or gameplay pops.

Validation checkpoint2433:1,124 unit tests pass (`/tmp/rcr-tests-2433.log`),
and `git diff --check` is clean. Review2430's70 flat source bindings and29
served artifacts were hash-checked; this does not remove the recursive-build
qualification limitation above or turn the diagnostic failures into passes.
