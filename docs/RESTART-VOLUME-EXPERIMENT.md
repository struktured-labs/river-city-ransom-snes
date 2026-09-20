# Restart volume experiment: isolated audio improvement, not deployed

[Native clips and waveform audit](http://127.0.0.1:8766/restart-volume-review-3400/).

The current phase80 game engine is still
`f22ccdd429c64fc8eb0f7e830ab8183fb938f0cbc85fe75babf11b0d371e009a`.
Its game candidate remains `build/sprite-fused-phase80-3342`. No console was
controlled or game cartridge changed during this experiment.

## Evidence and hypothesis

Current-game edge audit3385 reconstructs 2,056 selected native DSP samples exactly.
At sample1,727,946, frame3242, packet2845, pulse2 rises from volume0 to120 while
its old oscillator remains active. The volume stores precede KON and the staged
pitch stores. That is a measurable old-note burst, not yet attribution of the
user's physical pop. Several other strongest edges are ordinary noise/pulse
transitions. Do not classify every large waveform step as a defect.

## Actual prototypes and rejected results

`tools/build_restart_volume_trial.py` builds isolated packet players from the
current engine. It saves both calculated pulse volumes and delays pending-note
volume writes until after KON/pitch. The first guard rejected using $2F40 padding:
that region already holds the triangle fix. The implemented fixture instead
appends helpers, with equally padded control/trial uploads. It is not an
upload-length-preserving game patch.

Fixture3386 preserves all201,060 final-DSP/DP cases, but its state report3387
correctly remains failed: the historical writer-ownership interval excludes the
new helper. More importantly, actual waveform/onset3392 shows30 late-volume
restarts. The late-flush design is rejected and retained.

`tools/build_interleaved_restart_volume.py` constructs fixture3393, moving volume
writes directly after each voice's staged pitch and shortening the bounded wait
to8 iterations. Actual DSP observation, not the delay count alone, qualifies
this tested timing. Both arms upload12,608 bytes versus the game's12,415.

## Focused qualification

- Native ordinary packet replay:1,788 packets,36 period/duty/channel cases.
  Both voices, changing pitch, muted restarts, and unmute-with-restart are covered.
- Same-core observer on/off equality includes complete PCM, timeline, memory,
  screenshot, and actual received packet bytes. Raw DAC equals delivered PCM.
- All12 two-channel unmute cases improve from7–9 nonzero pre-note samples to0.
  The restarted note remains nonzero; a silent replacement fails the gate.
- All216 restarts retain correct first pitch/volume. All90 following samples
  per voice match their control in pitch, source, envelope, output and volume.
  This event-relative comparison does not assert full-mix equality.
- State3399:201,060 final-DSP/DP cases,16 continuous receiver/timer checks pass.
  The explicit writer interval includes new helpers; a restored legacy writer
  still fails. A wrong staged-volume source fails2,970 cases.
- Added publish/flush cost:63 SPC clocks without pending restart,39–40 with
  one pending voice,19–21 with both. Real-game timing remains unqualified.
- Injected native pre-note spike and silent-waveform controls fail acceptance;
  the first prototype's30 late-volume failures remain in the review.
- Full Python suite:1,352 tests pass in11.992s (`/tmp/rcr-tests-3401.log`).
  State check took3.79s; review validation/render generation1.87s. The HTML was
  served and visually inspected in Chromium.

The global native maximum adjacent step increases5399→7918. That event is away
from the restart and relative oscillator phases differ, but this is retained,
not normalized away or declared harmless. This is a local burst improvement,
not whole-mix, original-NES, subjective-listening, or pop-free acceptance.

## Next work

Qualify mute/update timing and additional DSP phases; integrate a bounded engine
upload change only with an appropriate control. Reproduce the actual game event,
then retest game cadence, scrolling/render/DMA and native game PCM. Physical
acceptance still needs an identified available capture route. Rivalmage remains
off limits; the last read-only check found another custom project on Bluemage,
and the OBS scene label did not establish console routing.

## Integrated game follow-up: delay13

The next iteration embeds the tested expanded engine with an explicit guarded
upload-count change. Pair3403 contains a padded original control and the delay8
trial; only the engine region, two upload-count bytes and checksum change.
The upload expansion was checked against the original builder's FF-filled ROM
padding, not presumed zero-filled RAM. No original graphics or gameplay code
was edited.

The actual-game delay8 replay exposes99 pitch stores before the verified silent
window, despite548 correct first pitches and no late volume. That narrower
first-pitch check was insufficient. The failed game/captures remain preserved.

Candidate `build/guarded-volume-game-3408/native-cpu.sfc` changes only the delay
from8 to13 iterations, plus checksum, relative to the integrated trial.
ROM: `ac0640cd708a62e2b7568f2c92e8f64e416bdd1b4154c0bf5279f18984275fae`.
Engine: `33d5d076f534779f6c693b9c2610c277d9dbb65ddd1a57793f3e3bbb0d8a666e`.
It is offline-only and has not been deployed.

[Actual-game prefix3416](http://127.0.0.1:8766/guarded-volume-game-review-3416/)
covers3,419 frames and3,022 received packets, including the original packet2845
case. All548 pitch and volume write sequences land inside observed startup
silence; first pitch and volume are correct. Both target volume registers stay
zero until silence, eliminating that voice's premature unmute. Actual native
full-mix clips use the same absolute sample interval without gain or alignment.
This does not attribute or certify the user's physical pop.

Original-counter, camera and requested/delivered input trajectories match the
equal-upload control. Busy-inclusive main-loop cadence is2 frames for601 room0
and485 room1 intervals. Rooms2/3 are explicitly missing in this prefix, not
passed. Seven transition-frame image differences,2,688 nonaudio timeline
differences and340 callback-boundary differences remain in the report.
The first changed images were rendered and inspected; they are transitional
flat-color boundaries rather than gameplay sprites. No broad renderer waiver
is inferred from that observation.

Guarded state3415 passes201,060 cases,16 continuous timer/receiver cases and the
wrong-volume/legacy-writer controls. Added publish/flush cost is63 clocks with
no pending restart,69–70 with one,49–51 with both. Fixture3414 retains216 correct
first pitches; additional checks find no early pitch or late volume there.
Python suite:1,357 tests pass in12.440 seconds (`/tmp/rcr-tests-3425.log`).

Full-route audio, cadence and renderer qualification is a separate follow-up;
do not inherit previous3342 DMA/menu/combat checks for this changed cartridge.

## Full route and remaining visible-text differences

[Full route3424](http://127.0.0.1:8766/guarded-volume-full-review-3424/)
covers9,248 frames,8,802 received packets, and1,611 restarts across all64 KON
phases. Every measured pitch/volume write is inside startup silence; no wrong
first pitch, late volume or stale nonzero onset. Original command sequences
match the padded control. Both recordings retain4,930,267 native stereo samples;
maximum adjacent step is4,335 control versus3,510 trial, with no clipping.
This is not an original-NES waveform or subjective pop-free verdict.

Busy-inclusive main-loop intervals remain entirely2 frames:601 school,
1,745 alley,477 mall,926 park. The renderer checks7,640 eligible frames with
zero missing lines, split cameras or stale cameras. Fresh DMA3427–3429 passes
56,333 complete envelopes:54,494 VBlank,1,835 forced-blank and4 other; latest
visible-frame end257. Active-scanout, crossed-frame and unfinished mutants fail.
This still excludes HDMA and physical hardware.

The combined strict3424 gate remains **FAIL**: logical camera snapshots differ
at7196/7204/7268. [Visual follow-up3430](http://127.0.0.1:8766/volume-visual-deltas-3430/)
verifies all3,828 committed camera values agree in frame/value/room/task/NMI,
and actual HDMA camera and full pictures agree at those three snapshots. These
are intermediate RAM differences, not evidence of changed final scroll output.
No old gate was edited or its result relabeled.

However, the complete24-image delta set includes real text-publication timing
differences. At6000 the trial shows `Grotto` while control is still typing
`Grot`; small dialogue glyph differences continue through6015. At8245–8248
the trial retains one more health-bar segment than control. Original game RAM
outside the stack-page range is equal at the inspected examples. This does not
prove which display timing is correct: trace original text/health generation,
tile publication and actual rendering before changing or promoting the port.
The page preserves all24 differences and zooms the first later-gameplay cluster
frames6000/8245. Both full and visual pages were rendered and inspected.

The first full-prefix comparison rejected an additional `waypoint_cursor`
telemetry field created by the full scenario. The corrected comparison verifies
every original field, independently reconstructs every added cursor from the
unchanged saved prefix picture, and retains all schema differences. Native
prefix PCM matches exactly. No primary state/video/audio field is dropped.
Three mutation-focused tests cover that schema distinction; the full suite now
passes1,360 tests in12.794s (`/tmp/rcr-tests-3426.log`).

Audit3424 took132.70s, substantially longer than replay. Repeated scans of all
DSP writes for each restart are a likely avoidable bottleneck; profile/index
those reads in a new verifier variant and compare complete reports before reuse.
All jobs are finished. No console or OBS state changed. Exact-build menu/combat
qualification, text timing resolution and physical acceptance remain open.

## Text publication diagnosis and full-ring scan experiment

Read-only full WRAM/VRAM captures3433/3434 completed, each with84 snapshots and
exact full9,248-frame same-core timeline/native-PCM neutrality. All98 bindings
per capture revalidated. The park health tile (nametable0, row2, column9)
changes BE→BF in the shadow at8242 in both builds. Equal-upload control stages
it at8243 and displays it at8245; audio3408 stages it at8245 and displays it
at8249. Thus the displayed difference is a real publication delay, not later
game damage or just a frame-boundary logical-camera sample. In this health
case the row flag remains1 (dirty, not staged), so the initial hypothesis of
an immutable OLD staged row blocking this particular update was not confirmed.
Dialogue row25 does have state3 intervals with older staged text pending.

Experimental `build/full-row-scan-game-3435/native-cpu.sfc`, SHA256
`486d0f1991362cd568c83ab578ddf78a2c5b9cc3c9cdaa87fd10b0a03f9fb63a`,
changes only the ordinary row-scan operand32→128 at ROM$838E plus checksum.
Hidden-transition scanning, DMA byte limits, row_room/final_room safety guards,
immutable stage ownership, SPC engine and original graphics remain unchanged.
It is a standalone unpromoted candidate, not a source-default or deployment.

[Source-to-picture audit3444](http://127.0.0.1:8766/full-row-scan-review-3444/)
retains all measured generations and initial/superseded/right-censored cases.
New compact direct-memory observer3437 samples HUD/dialogue shadow, staging,
VRAM and all128 flags every frame; full timeline/native PCM remains exact
against its unobserved same-core control. Its run took32.33s. Each of the three
selected health events also has a rendered-tile change checked against the
preceding picture, with full original pictures and diagnostic crops in the page.

The new route is9,121 rather than9,248 frames and encounters differ; no timeline
alignment, input equivalence, speedup percentage or matched-work claim is made.
The observed analogous park health change is shadow7943, staging7944, picture7947:
4 frames versus7 in audio3408 and3 in the equal-upload control. Therefore the
original-control latency gate remains **FAIL**; it correctly rejects3408 too.
All34 source-stable HUD tile changes and129 source-stable dialogue tile changes
in the trial publish within1–5 frames; these are tile-ID observations, not a
general palette/mirroring or whole-game graphics certificate.

New exact-build checks:

- Actual main-loop trace:3,684 busy-inclusive stable intervals, all2 frames
  (school598, alley1,745, mall478, park863). Not matched NES encounters.
- Audio:8,674 received packets,1,601 restarts, all64 KON phases; no wrong initial
  pitch, early pitch/volume, late volume, or stale nonzero onset. Native PCM
  retained:4,862,561 stereo samples, peak6,447, maximum adjacent step3,954,
  RMS1,228.57, no clipping. Different encounters prevent a waveform-improvement
  comparison with3408; restart timing is not subjective pop-free certification.
- [DMA3441](http://127.0.0.1:8766/full-row-scan-dma-audit-3441/):53,140 complete
  envelopes pass (51,311 VBlank,1,825 forced-blank,4 other), latest visible end
  line260. Less end-of-VBlank margin than3408's257; retain as a risk for further
  sprite/interrupt stress checks. All three unsafe-transfer mutants rejected.
- [Renderer3445](http://127.0.0.1:8766/full-row-scan-render-audit-3445/):7,512 eligible
  frames, no missing coverage, splits or stale cameras; exact observer neutrality.
-1,365 unit tests pass in12.010s (`/tmp/rcr-tests-3446.log`); whitespace check passes.

Audit3444 took39.44s. Packet-indexed calls reuse the existing startup-window
predicates without scanning unrelated DSP writes for every restart. This is not
a like-for-like benchmark against3424's132.70s, which verified two arms/prefixes.
The page was browser-rendered and inspected;247 source bindings and all generated
gallery artifacts revalidated. No console/OBS state changed. Next: get an exact
workload comparison for the remaining publication delay and stress sprite/final
batch latency before promoting full-ring scanning. Menu/combat, original-NES
fidelity and physical audio acceptance remain separate requirements.

## Matched workload results: scan expansion alone is not acceptable

Checkpoint3448 is neutral across the entire9248-frame audio3408 replay.
Fresh-process controls3449 (8232+32frames) and3451 (5980+50frames) reproduce
uninterrupted video, original RAM, PC/P/DB, inputs and exact native PCM/callbacks.
Trial wrappers verify all initial CPU registers, full WRAM/VRAM and exact allowed
ROM changes. Each variant takes roughly5.3–6.0s including cache authentication.
No restored instruction/DSP trace clocks are used. Commands are in
`docs/FOCUSED-TEST-CYCLE.md`.

[Matched comparison3465](http://127.0.0.1:8766/exact-row-scan-review-3465/)
supersedes the independent-encounter inference, not the retained prior reports:

- Unbounded128 (3435): exact health delay7→3 and dialogue2–3, but actual
  playfield pixels lag on8238/8239/8244/8245 despite equal sprite source/staging.
  Reject the tradeoff. Prior full-route DMA safety did not prove sprite latency.
- Bounded128 (3453, SHA09bb1c0fd627fe5e8d4a0201f14bd2a44e2af99f1562270f8a1e3fa596c5ca66):
  original row_room preflight on every scan block protects the playfield but
  dialogue becomes5–9frames instead of3–7. Health4. Bounded64 (3456) is the same
  in these windows. Reject both as an overall improvement.
- Unbounded64 (3458, SHA5600ca112c3f5de9669590f9e86c8b2e9df3c9e4a43a39c3d6a12cf5ce8e0c95):
  all11 exact-source dialogue glyphs take3frames; health4; playfield pixels,
  sprite source/staging, sampled game/NMI counters, cameras and inputs match
  throughout both windows. Full primary differences remain explicit; the
  older3-frame health target is still unmet.

[Broader follow-up3474](http://127.0.0.1:8766/row-scan-followup-3474/) rejects
promotion of3458 too: fresh sprite cycle3464 has19next-frame generations but
two2-frame generations (source1985/1987, rendered1987/1989). None is omitted.
Historical-prefix source/counter/camera/input comparisons also fail because
the boot-driven policy/encounters differ. Do not waive the actual late sprites.

Half-scan full route3462/3463 completes8883frames with exact observer neutrality.
Busy-inclusive stable main intervals are all2frames:598school,1746alley,
476mall,745park (3565total).8437 received sound packets,1554 restarts, all64KON
phases; no early/late/wrong first pitch/volume or stale nonzero onset. Native
PCM:4735678stereo samples, peak6501, maximum adjacent step4381, RMS1243.69,
no clipping. This is neither acoustic equivalence nor a pop-free claim.

## Sprite-first experiment and retained boot failure

3466 moves the exact544-byte OAM transfer ahead of background searching, gives
rows three previously consumed OAM scanlines (cutoff246→249), retains the late
palette deadline251 and full128-entry search. It failed with large palette
corruption: the original late OAM block also initialized DMA mode0 and bank7E
for CGRAM; intervening background/CHR work can overwrite those registers.

3469 explicitly restores both palette preconditions. ROM SHA
e705fe1764e3929a3cadd3eff5e0285a52465dbf33e55c472359bd0df7419009.
Its exact-state health/dialogue replays3470/3471 preserve all playfield pixels,
sprite source/staging, counters, camera and inputs. Dialogue2–3frames, health5.
But fresh sprite-prefix3472 and independent full-route attempt3473 both fail
to reach the story image within the existing deadline:3119frames, ending on a
black picture, no adapter fault. The failure cause is not yet established.
This candidate is rejected; restored gameplay success cannot qualify its boot.
No broader DMA/audio campaign was launched for that failed boot candidate.

Current conclusion: scanning more cannot be accepted on its own, and an OAM
reorder must preserve menu/transition behavior and all DMA register dependencies.
Investigate that boot failure or a lower-cost ready-row discovery mechanism;
do not compensate by weakening visibility, sprite-generation or cadence gates.
No new variant is promoted/default/deployed. The full speed/scroll/audio goal
remains open, including physical audio, menus and broader combat qualification.

Reports3465/3474 were rendered and inspected;73/725 source bindings and gallery
artifacts revalidated.1,371 unit tests pass in13.481s (`/tmp/rcr-tests-3475.log`);
whitespace check passes. All processes finished. No MiSTer or OBS state changed.

## Transition/display commit follow-up (3502, September 19)

The sprite-first boot failure is now explained by actual saved PPU state:
the working parent and failed3469 have identical VRAM and prepared palettes,
but3469 retains INIDISP80/main-screen00 and the old settings CGRAM. Returning
three already-spent OAM scanlines to the palette-only final guard (251→254)
restores boot in3479. Review3492 retains that diagnosis and its limitations.

3479 then exposes a transition consistency bug: transition_ready clears1CA0
before final_room admission. If the final batch is rejected, the transition
is reported complete while hardware remains blank. The first room transition
has one missing-coverage frame2424 in the strict renderer audit.

3502 makes that handoff atomic, restoring the previous transition state when
final admission fails. The exact same64 transition words are read using the
publisher's existing DP1E00, saving64 CPU cycles; the12 CHR words are unchanged.
This is not a cached-ready flag and no dirty word is skipped. Cutoff stays254.
ROM SHA256:
`e8a6b2f57702fe2057276aa506917b4aa264c5de0dc3acf1d4893b4749cc40b4`.
Builder: tools/build_transition_commit_direct.py, pinned to3479. The native
trampoline source is snes/transition_display_commit.asm. Experimental only;
default build and MiSTer remain unchanged.

Two intermediate failures are retained:

- 3493: rollback plus cutoff254 stalls at settings. Repeating the expensive
 readiness scan prevents final admission indefinitely.
- 3498: cutoff255 restores boot but latches VBlank overrun at frame2435.
 Do not promote it or inherit3502's safety verdict.

[Compact full audit3518](http://127.0.0.1:8766/transition-display-summary-3518/)
links immutable detailed3517 evidence with1,232 validated source bindings.
Fresh boot-prefix normal/observed runs take6.20/6.53seconds. Both complete
2,578frames; the parent takes2,577frames. Full primary differences are retained,
not aligned away. The first room's normal fade is20 black frames in BOTH builds;
room-entry→first-visible is21frames in both. The first visible picture matches
exactly. This improves display/state consistency, not fade duration.

Current3502 qualification:

- Full9,089-frame renderer route, same-core full video/state/input/native PCM
 equality:7,476eligible playfield frames, no missing lines, splits or stale
 camera failures. This does not certify every tile/CHR/color/menu.
- 52,741 full general-DMA envelopes safe;50,843VBlank,1,894forced-blank,4other;
 latest visible transfer end line258. Unsafe/cross-frame/unfinished mutations
 fail. HDMA and physical per-byte validation remain separate.
- 21 sprite source generations through2020 render next frame, with observation
 through2024. Later and censored sources remain recorded. A removed-generation
 mutation fails. This is not cross-ROM identical-encounter speed proof.
- 8,641 audio commands,1,585 restarts, all64 startup phases: no tested first
 pitch/volume ordering errors.4,845,501 native stereo samples retained; peak7010,
 max adjacent step4714, no clipping. This does NOT establish pop-free acoustics.
- 3,667 busy-inclusive stable game-loop intervals are all2frames:598school,
 1,746alley,476mall,847park. Exclusions/censored boundaries remain in JSON;
 this proxy is not matched original-NES performance acceptance.

[Exact row guard3521](http://127.0.0.1:8766/transition-direct-row-review-3521/)
retains an overall FAIL for the unmet health target. Authenticated32/50-frame
replays take5.76/5.80seconds and preserve all playfield pixels, sprite source/
stage, sampled counters/cameras and inputs. Dialogue delays improve from3–7
to2–3frames; health is7→5frames relative to audio3408. The earlier equal-upload
control's3-frame health target remains unmet. No complete primary cross-ROM
equality is claimed: audio/register/game-RAM differences remain recorded.

1,382 unit tests pass in13.992seconds, including seven new assembled-helper/
flag-equivalence fixtures. The current candidate is NOT deployed or release
ready. Remaining work includes health publication latency, current menus,
matched original-speed workloads and physical/acoustic acceptance. No MiSTer,
OBS, user captures, or default cartridge were changed.

### Important follow-up:3502 still starved CHR

The completed-DMA and renderer checks above did not cover pending CHR liveness.
Further inspection found two graphics-pattern jobs held for3,513 visible frames
in3502. Candidate3527 returns the three early-OAM scanlines to CHR admission
(243→246), and verifies source-equal bytes in actual VRAM within2/3frames.
It retains the3502 transition fix and unchanged row/palette deadlines.
See [EARLY-OAM-CHR-PUBLICATION.md](EARLY-OAM-CHR-PUBLICATION.md) for raw-state,
full-route, negative-control and exact-pixel evidence.3502 is not promoted;
3527 also remains experimental, including the still-unmet health latency goal.
