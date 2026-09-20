# Port milestones

The requested outcome is a playable native SNES conversion with unchanged NES
graphics and NES-style SPC sound. The audio diagnostic is an initial milestone,
not completion of that outcome.

1. **Implemented: foundation.** Strict original-ROM profile, lossless tiles,
   reproducible assembly, SNES boot and SPC pulse diagnostic, data tests.
2. **Partially implemented: program map.** Original US ROM located on Bluemage;
   authenticated title/street traces drive 178 hardware/RAM-code patches. Record reset/NMI/IRQ, decode reachable
   code in all 16 PRG banks, identify banked data and indirect call tables.
   Inventory PPU/APU/controller/MMC3 reads and writes with traces. Rebuild the
   unmodified NES image byte-for-byte before changing instructions.
3. **Implemented experimentally: native boot and title.** Choose game memory map, implement bank switching,
   interrupt adapters, hardware access hooks, tile/palette/OAM upload and input.
   Match the original title with original assets and timing.
4. **Street reached; incomplete slice.** Match street scrolling, HUD split, two players, enemies,
   shops and transitions. Preserve original sprite data, animation and controls.
5. **Game audio transport implemented; fidelity open.** Route original audio-driver writes through an event-aware APU
   bridge. Verify both pulses, triangle, noise, length/envelopes/sweep, silence
   and any DMC usage. Evaluate the Myself086/newer engine with matching protocol.
6. **Full-game validation and patch.** Play through with deterministic input,
   compare against NES captures, test real SNES, generate a source-ROM-validated
   patch and publish reproducible build instructions. Never substitute a renamed
   NES image or a diagnostic for the actual game.

## Current reported regressions

- [Integrated audio fast-poll candidate4108](TIMED-TOKEN-GRACE.md):
  the previous integrated receiver4098 failed12 three-frame mall intervals
  and a33.833ms ready gap. Bounded16-iteration token polling now completes
  the full9,092-frame route with all3,668 measured school/mall/alley/park
  intervals at two frames, observer-neutral native PCM, and stable ready
  gaps15.313–18.084ms. Isolated arrival-boundary cases pass. 1P combat
  including-busy and Present Status pass. 2P combat still has14+3 three-frame
  stable intervals (~24k extra clocks vs3955); a64-poll trial did not move
  them. DMA 52,470 envelopes and shop two-purchase pass. Immediate-commit
  clears 2P jumps but worsens 2P attacks. Not promoted: 2P standing combat,
  popping and hardware remain open.
  [Review4115](http://127.0.0.1:8766/timed-token-grace-review-4115/).
- [Sprite-copy preparation and focused test cycle](SPRITE-COPY-PREPARATION.md):
  candidate3252 fixes the matched sprite-publication window: all20 known
  generations appear next frame, versus four three-frame delays and five
  unrendered generations in3219. The one-command focused cycle takes15.54s;
  the actual old cartridge fails its symptom gate. Broader exact-build checks
  pass3,750 cadence intervals,7,639 eligible renderer frames,56,205 DMA
  envelopes,1,607 sound restart windows and all four menu suites. Broader
  two-player running/jump stress then catches one three-frame interval at
  frames2239–2242 (3292);3252 remains experimental.1,326 tests pass including
  the new AI/shop/tracker tests. Broader NES equivalence and physical audio/video
  remain open; no hardware touched. The reusable
  `romhack-test-loop` skill is installed. AI-assisted P2/equipment routing is
  implemented as an isolated tested prototype, not included in this qualification.
- [Video-stage diagnosis and lower-cost restart staging](STARTUP-STAGING-VIDEO-TIMING.md):
  3190 passes all four menu regressions and56,233 general-DMA envelopes. New
  paired background/WRAM observations isolate timing-sensitive sprite and
  palette preparation differences. Implemented3219 reduces ordinary helper
  overhead32→13 SPC clocks per active pulse;201,060 state cases and all1,607
  actual game restarts pass. Changed images365→321, prepared-sprite snapshots
  77→55, but callback differences830→884 remain.1,306 tests pass. Exact3219
  menus/DMA/renderer/combat were subsequently qualified in review3250;
  actual sprite-publication lag motivated3252 above. Physical audio remains
  open; no hardware touched.
- [Full-game restart-pitch staging trial](COMPACT-STARTUP-PITCH-GAME.md):
  candidate3190 preserves upload length and all8,802 complete CPU packet
  records; all1,607 actual game restarts pass startup-silence timing. Four-room
  cadence, same-core renderer coverage, and both two-player combat policies
  pass.1,300 tests pass.365 changed images and830 callback differences remain
  documented; current-ROM menus, DMA, broader fidelity and physical capture
  remain open. Neither MiSTer touched; not promoted or deployed.
- [Offline restart-pitch staging prototype](STARTUP-PITCH-STAGING.md):
  actual SPC staging moves restart pitch writes into verified startup silence.
  All200 tested restarts and201,060 state cases pass; executed early/late
  variants fail timing checks. Costs up to250 extra SPC clocks, cross-arm
  callback differences, and the existing low/narrow NES-reference failure
  remain.1,295 tests pass. Not integrated into3065 or deployed to hardware.
- [Current-game pre-restart pulse observation](CURRENT-GAME-PRE-RESTART.md):
  neutral9,248-frame captures reproduce prior DSP clocks/PCM exactly. All4,600
  selected DAC samples reconstruct through all eight voices;36 timing-selected
  restarts contain three split-pitch samples, one with nonzero output at
  packet6,222. This is a current-game instance of the known non-atomic update,
  not a physical-pop diagnosis.1,289 tests pass; cartridge/hardware unchanged.
- [Executed NES volume-write sensitivity](NES-VOLUME-SUPPRESSION-SENSITIVITY.md):
  selectively omits323 zero writes across204 same-mode runs while preserving
  all8,548 game frames, CPU clocks/write intents, RAM, video and sample timing.
  Native PCM differs in189 selected windows; local step changes go both ways
  and the global maximum changes by one unit. Fidelity effect established,
  physical-pop cause not established.1,283 tests pass; no SNES ROM or hardware
  change. Investigate actual note-transition behavior before transport changes.
- [Original sound-driver write timing](ORIGINAL-DRIVER-WRITE-COALESCING.md):
  fresh observer/control captures retain all37,457 NES APU writes,7,898 wrapper
  calls and766 outside writes. Current3065 preserves8,802 final packets and
  5,650 metadata events, but coalesces377 changing-register groups. Original
  NES has285 in-driver zero-volume→nonzero intervals of314–2,196 CPU clocks.
  This narrows a fidelity experiment, not a physical-pop diagnosis.1,276 tests
  pass; no game change, MiSTer access or OBS operation.
- [Executed prototype noise-attack correction](NOISE-SOURCE-FIRST-CORRECTION.md):
  source/pitch now precedes nonzero volume; zero commands mute both channels
  before source changes. Corrected2x/8x engines match all eight fallback-noise
  cases, pass1,792 held noise packets each and reject44 ordering violations in
  each old engine. Enabled-zero transitions execute separately and pass.
  1,271 tests pass. Shortened loop/startup/spectral limits still prohibit
  promotion; game cartridge unchanged and neither MiSTer accessed.
- [Noise bit-hold experiment](NOISE-INTERPOLATION-CONTROL.md): paired offline
  2x/8x BRR fixtures retain identical bit prefix, code, upload length and packet
  timing.8x centroid is closer to NES in20/20 cases versus2x, but only13/20
  versus the current engine. A two-sample attack comparison exposes late NON
  source selection after volume in the hybrid prototype. Shortened noise loop,
  startup cost and retained failures block promotion.1,266 tests pass; game
  engine unchanged, no hardware operations, physical popping still unproven.
- [Current four-room and original-audio timing](ORDINARY-ROUTE-TIMING.md):
  unchanged3065 passes all3,750 selected two-frame gameplay intervals across
  four rooms with NMI-busy retained in the selector. Fresh original NES sound
  trace has7,087 selected consecutive one-frame driver entries; driver return
  timing varies in the original too, not a pop-free waiver. School-return
  audit matches all40 background offsets and first visible+7.1,262 tests pass.
  Independent encounters are not equal-work speed proof. No hardware touched;
  Bluemage capture path and physical audio acceptance remain open.
- [Expanded audio-trial qualification](ORDINARY-AUDIO-EXTENDED-QUALIFICATION.md):
  unchanged3065 now passes all four menu regressions and sustained-attacks
  combat as well as running jumps. A new observer checks56,245 general DMA
  envelopes across the exact9,248-frame route; none is aborted or unsafe/
  unproven for display memory, latest visible end257.1,257 unit tests pass.
  Bluemage/OBS inspected read-only; physical capture connection unconfirmed.
  Rivalmage untouched. Pop-free physical audio and full-game speed remain open.
- [Ordinary-path early audio trial](ORDINARY-EARLY-AUDIO.md): offline3065
  moves eligible normal-path sound service before the original game interrupt
  body. All8,802 ordered packet payloads/native IDs remain identical to3032;
  completion-interval standard deviation drops71.36% over the same7,609 event
  pairs.44 interrupt/ABI fixtures, fresh combat, scrolling, Present Status,
  pause onset and both saved-state picture-recovery checks pass.1,253 unit
  tests pass. Other menus, whole-schedule DMA margin and physical audio remain
  open; neither MiSTer touched and no pop-free/release verdict.
- [Current audio pipeline timing](CURRENT-AUDIO-PIPELINE-TIMING.md): unchanged
  offline3032 has8,802 complete receipt/ready pairs. Across7,609 gameplay
  intervals, arrival gaps span11.93–21.15ms; post-receipt service changes
  contribute−0.68 to+0.84ms. Most measured cadence variation is already
  present at receipt; its upstream stage and audibility remain unproven.
  Frozen audio events retain exact timing context.1,247 unit tests pass;
  neither MiSTer touched and no new ROM/deployment or pop-free claim.
- [Current menu, dense-DMA and waveform qualification](FINAL-BATCH-QUALIFICATION.md):
  unchanged offline3032 passes all four fixed NES menu oracles across19,990
  frames.156 expanded and1,024 dense final-batch cases pass; live palette
  conversion can finish at261, a tighter margin than the earlier257 result.
  Fresh same-core stems show noise dominates6/12 selected audio steps, other
  voices6/12; all native clips and completion-cadence variation are retained.
  These edges are not yet identified as defective pops.1,243 unit tests pass;
  no hardware deployment or full speed/audio-fidelity claim.
- [Final sprite/palette deadline recovery](FINAL-BATCH-SLACK.md): offline3032
  restores the earlier fixed-picture gate while keeping the fresh combat pass
  (1,753 two-frame intervals). The missed OAM DMA is traced to the line250
  cutoff; one-line slack passes18 actual full-batch/physical-OAM cases, ending
  by257. Full9,248-frame scrolling and8,802-packet DSP ordering checks pass.
  Two scan-stopping alternatives are retained as failures. Menus, broader
  timing margins, audible popping and physical qualification remain open.
- [Owned-queue preparation priority](OWNED-QUEUE-PRIORITY.md): offline2990 now
  passes the fresh4,929-frame running-jump cadence test, with1,753 two-frame
  intervals and no busy-inclusive irregular interval.192 guard cases and two
  predecessor negative controls pass. Scrolling and ordered event/packet checks
  pass; the earlier2239 picture gate still fails and pop-free audio is unproven.
  No hardware deployment; Rivalmage remains off-limits, Bluemage permitted.
- [Retained event ownership and active-frame wait](RETAINED-EVENT-OWNERSHIP.md):
  offline2971 preserves the older job's audio identity and queues the newly
  arrived hardware event.44 vectored-entry cases,36 beam cases and four executed
  negative controls pass. Same-state trace has all seven original bodies and
  seven ordered sound packets; completion advances one frame earlier. Full
  traversal/scrolling checks pass. Fresh combat still has one three-frame start
  interval, and the earlier2239 fixed-picture gate now fails despite recovered
  counters.1234 unit tests pass. No promotion; Rivalmage is occupied/off-limits,
  Bluemage is the user's permitted next hardware target.
- [Queued real VBlank service](QUEUED-VBLANK.md): candidate2916 recovers the
  exact2239 saved-state stall.130 queue and104 priority cases pass; six executed
  faults are rejected. Actual trace proves three real acknowledgments/services
  and nine ordered sound packets. Full-route scrolling and all four menu
  regressions pass;8802 audio packets/1607 restarts validate. One fresh combat
  three-frame interval remains. Cheaper read polling2944 saves120 clocks per
  measured call and retains recovery, but still has one combat gap. Neither
  is promoted; Rival2648 unchanged. Web collages2943/2957 retain failures and
  audio. Fresh full trace confirms hardware NMI on all three frames of the
  remaining gap: main/interrupt/preparation completion is late, not another
  lost hardware entry. Audit2959 then locates the executed single-slot fallback:
  it serves the retained body but leaves the new event unscheduled (three
  hardware entries, two original bodies). Preserving both event jobs without
  duplicate sound is the next repair target.1228 unit tests pass.
- [Restore-local interrupt clock](RESTORED-INTERRUPT-CLOCK.md): four90-frame
  replays match their old-core outputs; enabled tracing is independently
  neutral for full WRAM, all registers, frames, two-port inputs and native PCM.
  Every trace reconstructs from2358 real line events. The pending VBlank flag
  expires while masked in the exact2239 stall for all four variants, including
  new fusion+dirty2894. The best body return is still3486 clocks past wrap.
 1215 tests pass. A real-event collector remains to implement; no deployment.
- [Full PPU stub fusion](PPU-STUB-FUSION.md): each of two candidates passes432
  complete caller/return/NMI-policy cases and four executed negative controls.
  Measured full calls save444–592 clocks. Both still fail the same-state2239
  stall; combined2869 passes fresh combat but retains two uneven westbound
  camera holds. Fusion-only2868 keeps steady short-hold pacing but still stalls
  once in combat.1208 unit tests pass. Neither is promoted; Rival unchanged.
- [Common PPU write fast paths](PPU-REGISTER-FAST-PATH.md):270 helper comparisons,
  246 independent checks and four executed mutants; targeted variants preserve
  unrelated I/O. Five measured calls save204–280 clocks. Combined2850 passes
  fresh running/jumping combat, but all four saved-state trials still miss2239,
  and combined scrolling retains two uneven westbound holds. Write-only2849
  keeps steady scrolling but still has one combat stall.1,203 tests pass;
  neither is promoted, and Rival2648 remains unchanged.
- [Ring copy/dirty-cache trials](RING-DIRTY-CACHE.md): two offline candidates
  each pass217 executed memory comparisons and180 independent checks. Measured
  vertical copies improve35–36%, but neither recovers the saved-state stall.
  Both full routes complete; tile-only has two short irregular westbound
  camera holds despite no split/stale-camera failures.1,200 tests pass.
  Keep2769 as the offline baseline; Rival2648 is unchanged.
- [Balanced phase96 timing](PHASE-BALANCE-VALIDATION.md): offline2769 retains
  one exact-state frame recovery with zero short irregular park holds and
  all961 camera changes at the parent's two-frame main-to-display latency.
  All four menu regressions and8432 audio packets pass. One combat stall
  remains; the new busy-NMI summary prevents its accidental exclusion.
  Copy-cache combination2796 does not fix it and fails the full route.
  1,197 tests pass; Rival remains unchanged on2648.
- [Earlier main-loop reprobe](MAIN-PHASE-REPROBE.md): phase64 recovers one
  exact-state missed interrupt; another remains. A camera-cutoff follow-up
  retains that recovery, but both are rejected for scrolling jitter. Full
  routes and sound transport pass; actual camera timing alternates between
  one and two frames from main start.50 phase and86 camera cases execute;
  1,193 tests pass. Both remain offline; Rival unchanged on2648.
- [Vertical PPU pointer cache](RING-STRIDE-CACHE.md): offline2715 reduces two
  measured20-byte copy calls by23–24%;111 executed comparisons and90 independent
  CIRAM/dirty/ABI cases pass. It does not fix either targeted saved-state stall.
  Running2P combat still has two gaps; full-route qualification fails after
  losing all power in the park and returning to the mall.1,185 tests pass.
  No full-route audio/scrolling claim or promotion; Rival remains on2648.
- [Complete masked-path budget](MASKED-PATH-BUDGET.md): offline2696 changes
  both producer admission immediates to120. Two exact-state failures each
  recover one game frame;129 executed cases and three negative controls pass.
  Full-route renderer and8,432 audio packets validate;1,181 tests pass.
  Running2P combat still has three gaps. New traces prove the original retained
  interrupt alone can cross VBlank when entered late; a graphics cutoff cannot
  solve that path. No promotion; Rival remains on2648.
- [Retained producer interrupt guard](RETAINED-PRODUCER-GUARD.md): offline2673
  recovers a traced missed VBlank from the same saved combat state; the affected
  update completes one frame earlier. Two-player stable three-frame gaps fall
  18→0 and12→3 in independent encounters (not matched-work speed ratios).
  Full-route renderer checks pass7,266 eligible frames;8,432 sound packets and
  1,548 restarts validate.1,178 unit tests pass. Three combat gaps remain;
  menus, physical scrolling and pop-free audio still require qualification.
  Rival remains on harmonic splash2648, unchanged by this experiment.
- [More pronounced splash WUB](HARMONIC-WUB-TAIL.md): candidate2648 adds
  nonlinear overtone motion over the existing fixed55 Hz, three-pulse tail.
  Native emulator review2650 passes13 gates; graphics/game audio after handoff
  remain exact. Small pre-tail PCM/callback timing differences are retained.
  Before/after audition and collage are available;1,169 tests pass.
  Deployed to Rival with receipt2654; native hardware review2659 passes all
  five tail gates and retains the previous quiet-slide pitch-check failure.
  SNAC Yes verified2665; saved settings and OBS audio routing unchanged.
- [Binary BRR noise prototype](BINARY-NOISE-PROTOTYPE.md): all three NES quality
  references retain the observed spectrum gap, with actual quality modes and
  integer filter output verified. Offline SPC prototype2614 replaces built-in
  noise with a binary LFSR sample;1,238 packets and243 pulse onsets validate.
  Do not deploy: centroid improves in6/11 windows but regresses in5/11, noise
  peaks roughly halve, and startup is39 frames later. Reviews2613/2622 retain
  all clips and failures.1,161 tests pass; production2367 unchanged on Rival.
- [Current noise state reference](CURRENT-NOISE-PACKET-REFERENCE.md): executes
  all1,238 recorded packet frames on NES within a strict constant-volume,
  length-held scope; not original-write reconstruction. Fresh current-SPC
  isolation preserves nonaudio execution. All11 retained transient windows
  have higher SNES spectral centroid (1.317–1.900×); this is not a pop verdict.
  Same-core filter observation reconstructs998,292 samples exactly and shows
  the difference already exists before the NES output IIR. Native clips2598
  and filter review2603 retain exclusions and limitations.1,156 tests pass;
  production2367 remains on Rival, unchanged. Noise generation/downsampling,
  not generic output smoothing, is the next synthesis investigation.
- [Camera-recorder qualification](CAMERA-RECORDER-QUALIFICATION.md): mapping-only
  control matches every timeline row and native PCM; executing even the
  recording-disabled wrapper changes timing. Idle-time alternative fails to
  reach the street. Both remain offline; physical four-frame hold unresolved.
  Follow-up traces prove and repair an opcode/displacement patch error.
  Moving recording into the original wait completes9,225 frames; actual camera
  scanlines match in all7,618 eligible game frames. One extra disabled-BG
  event,15 sprite-picture differences and PCM changes remain explicit.
  Camera-only scoped evidence is not full neutrality. Boundary fixture2457
  passes134 cases and rejects four mutants. Temporary Rival startup2461
  exports29 records; traversal guard2487 rejects before input. Normal2367
  restored by receipt2490; no physical camera-hold attribution yet.
  Successful follow-up2520 exports265 new samples, with exact paused resave.
  Video does not reproduce the four-frame hold. Although226 adjacent two-tick
  pairs satisfy the commit/shadow relation, only three change the working
  camera;38 sampling gaps prevent scrolling qualification. Review2546 retains
  all video/sample gaps. Normal2367 and SNAC restored;1,142 unit tests pass.
  Extended-window2547 offline qualification:168 boundary cases pass, four mutants
  rejected; moving-camera two-tick coverage rises208→691 on the same route.
  Review2552 matches all160 scanlines in7,618 eligible frames, but retains two
  other renderer differences,48 picture differences and changed PCM. No
  physical hold attribution or audio qualification;1,147 unit tests pass.
  Physical follow-up2573 exports493 new records;61 moving-camera neighbor
  pairs satisfy the commit/shadow relation, with57 gaps (maximum22 NMIs).
  Review2594 retains the full video, fixed collage and ten rejected pairs.
  The earlier four-frame hold was not reproduced or explained. Production2367
  restored2586, SNAC Yes verified2588, OSD closed2592;1,149 unit tests pass.
- [Current physical gameplay](CURRENT-PHYSICAL-GAMEPLAY.md): combined2367
  traversed on Rival with native audio.39.95-second paused capture is entirely
  silent, with non-dead gameplay control. One four-frame camera hold and all
  audio transients remain visible. Delayed pause sound occurs at+57 frames in
  both original NES and current emulator candidate; new negative controls pass.
  SNAC restored, game paused, settings unchanged.1,120 unit tests pass.
- [Combined speed + deeper splash deployed](SLOW-WUB-TAIL.md): Rival now runs
  compact-sub-wub2367 (compact-pair2242 gameplay, unchanged production sound
  engine,55 Hz ident). Native hardware2375 passes all five tail checks: three
  deep half-second pulses, steady note, decay and no clipping. One quiet-slide
  pitch checkpoint fails; report retains it. Saved SNAC/OBS settings preserved.
  Gameplay speed and popping still need physical qualification.
- [Current speed-candidate menu regression](CURRENT-COMPACT-MENU-REGRESSION.md):
  19,990 fresh frames; status opening/reopening, repeated purchases, shop NO
  selection and pause-cursor return pass original fixed-region/VRAM oracles.
  Known-broken controls still fail.1,116 unit tests passed at that checkpoint;
  the subsequent combined deployment is recorded above.
- [Like-for-like alley load counters](LOAD-COUNTER-COMPARISON.md): fresh neutral
  NES/SNES traces both span15 frames, reset original `$010B` at+13 and finish
  at tick2. Historical SNES8-versus-NES2 compared different counters. Full
  load-to-visible timing and all40 fade offsets match;1,655 running/combat
  loops pass a separate reference-context gate with late-frame mutants.
  Historical strict FAIL retained; no physical/full-game certification.
- [DC trial rejected by recorded gameplay commands](DC-PULSE-COMMAND-REJECTION.md):
  same1,238 physical commands and46,365 exact-clock DSP writes; noise remains
  sample-identical. Four of eleven fixed event windows have19–44% larger
  absolute steps. Do not promote the isolated-tone pass as a popping fix.
  Production/Rival unchanged; original speed candidate2242 remains the base.
- [Zero-DC pulse trial](ZERO-DC-PULSE-TRIAL.md): exact waveform centering with
  compensated AC level; all eight scoped pulse cases pass. All9,225 full-route
  game/timing rows match,371,584 DSP writes retain clocks, and noise/triangle
  PCM are unchanged. Some absolute pulse steps increase; an executed quiet
  control fails the loudness gate.1,111 tests pass. Offline only, physical
  popping and full-game qualification remain open.
- [Current pulse-reset NES reference](CURRENT-PULSE-RESET-REFERENCE.md): eight
  duty/pitch cases with exact current SPC, executed NES and same-core observers.
  Seven pass existing transient bounds; low/narrow duty fails relative step
  (1.0 versus0.883850 limit). Hardware-context duty3 passes that metric, not a
  pop-free verdict. DC differences retained;1,103 tests pass. No deployment.
- [DSP voice-edge reconstruction](DSP-VOICE-EDGE-RECONSTRUCTION.md): all2,827
  selected stereo replay samples reconstruct exactly through eight voices and
  master/echo mixing; independent noise stems match. Noise controls stay steady
  at all11 selected peaks; two pulse-2 edges coincide with correctly delivered
  restart silence boundaries, not mixed pitch.1,099 tests pass. Physical pops
  remain unresolved; next compare current restart waveforms against NES.
- [Native transient channel isolation](NATIVE-TRANSIENT-STEMS.md): fresh exact-
  command replay validates current speed candidate's two-byte SPC difference;
  all1,238 completion register states agree, while waveform/timing differences
  remain visible. Noise dominates8 of11 covered replay transient windows; no
  physical pop is declared resolved. Native clips and fixed-scale plots published;
  1,094 tests pass. Rival unchanged; continuous noise/pulse DSP state is next.
- [Current park-hold origin](CURRENT-PARK-HOLD-ORIGIN.md): all19 long current
  SNES park holds are repeated game camera commands with complete two-tick
  loops and next-frame display, not missed renderer updates. Fresh original
  NES control explains18 analogous holds. Every interval retained; independent
  encounters and the older physical hold are not declared equivalent.1,087
  tests pass; native audio transients remain open.
- [Compact paired-row reprobe](COMPACT-PAIR-REPROBE.md): identical-state school
  replay removes a3-frame update (now2) and corrects scenery8→7.1,024 actual
  production-byte VRAM cases and1,081 unit tests pass. Full-route fades,
  7,618 renderer frames,3,741 stable loops and audio transport pass.15-frame
  alley load and13 long park holds retained; still offline, physical pops open.
- [Camera deadline reprobe](CAMERA-GUARD-REPROBE.md): sustained combat now
  passes1,661 measured loops; all3,510 eligible stable frames retain one NMI.
  Two late graphics jobs defer and complete exactly once. School/forward fades,
  renderer and DSP checks pass; running/jumping still has three timing failures.
  36 executed beam cases and1,075 unit tests pass. Offline only; empirical
  deadline is not a worst-case proof, and physical popping remains unresolved.
- [Palette-compare speed correction](PALETTE-COMPARE-SPEED.md): school return
  now matches all40 NES fade offsets at+7; forward fades,7,266 renderer frames,
  3,565 stable loops and8,432 audio packets pass.17,408 executed helper cases;
  1,067 unit tests pass. Strict combat finds a stable3-frame gap and retained
  transition stalls. A neutral instruction replay traces the stable gap to
  deferred graphics masking NMI from line238 through next-frame17. Offline
  only; physical popping remains unresolved.
- [Unused-sprite hiding optimization](OAM-HIDE-TAIL.md):131,072 executed
  equivalence cases pass; first measured hide call7,038→1,704 clocks.
  Full traversal completes and all3 forward fades match all40 NES offsets.
  School return remains+8 versus NES+7; late palette generation and the
  interrupt-crossing final main call are traced.1,060 tests pass, offline only.
- [School fade scheduling probes](SCHOOL-FADE-PROBES.md): eight smaller cap
  pairs do not meet NES timing. One/two bounded early preparation passes improve
  return fade9→8, still failing NES+7; one-pass forward route also times out.
  Both512-case helper ABI checks pass, but neither candidate is deployable.
- [Controlled school return](CONTROLLED-SCHOOL-RETURN.md): same-state replay
  confirms the three-frame load saving, but a new actual NES return reference
  exposes scenery at enable+9 versus NES+7. Shorter whole loading does not waive
  this fade regression; target post-return scheduling next. No deployment.
- [Saturating-shift speed trial](SATURATING-SHIFT-TRIAL.md):983,040 executed
  arithmetic cases; school-return interval26→23 frames on the older branch.
  Newer scheduling passes room fades,3,739 stable loops and7,616 renderer frames,
  but strict combat load timing still fails. Offline only; audio pops remain open.
- [Slower fixed-note splash ending](SLOW-WUB-TAIL.md): three deeper WUB pulses
  deployed on Rival with native audio/OBS evidence. Offline boundary regression
  passes; physical first peak interval fails the strict spacing gate (27 versus
  minimum28 nominal frames). Gameplay unchanged; subjective approval pending.
- [Current-engine native command capture](CURRENT-NATIVE-COMMAND-CAPTURE.md):
  validated pre/post/repeated physical exports retain1,238 consecutive commands;
  2,398 native PCM pairs match common input exactly. Same-engine replay supports
  commanded rests for two short gaps, not a global pop-free verdict. Video,
  collages, native clips and DSP context published. Regular build restored,
  SNAC Yes; latest speed/graphics candidate remains offline.

- [Boot-anchored native physical menu audio](NATIVE-MENU-BOOT.md): fixes a test
  harness limitation by capturing complete HDMI reacquisition packets in bounded
  chunks.2,390 physical input/common pairs match exactly;22 held-out menu seconds
  show no large missing-energy bins and injected silence/clock-slip controls fail
  as expected. Rejected old capture retained;1,017 tests pass. Same regular
  cartridge restarted for diagnosis, no new ROM or settings changes. Smaller
  clicks, gameplay SFX, and physical speed/scrolling remain open.

- [Active-loop hidden-row trial](ACTIVE-HIDDEN-BUDGET.md): conditional15/16-row
  scheduling restores all3 room-entry fades to NES+7 with all40 offsets exact.
  Fresh checkpoint controls establish same-state causality;3,662 stable loops,
  7,460 rendered frames, audio transport, Status and shop/cursor regressions pass.
  Fresh sustained combat passes1,661 loops; running combat retains a15-frame
  transition failure. Separate entry audit matches NES20-frame total visibility
  and all40 fade offsets, without waiving that strict gate. Native failure
  audio and collages published;1,010 tests pass. No Rival/OBS changes, promotion,
  or pop-free/full-speed claim.

- [Post-load scheduling and checkpoint qualification](SHIFT-FADE-SCHEDULING.md):
  exact alley trace identifies a one-scanline shift crossing the end-of-loop
  interrupt boundary; mall evidence shows unequal actor work, not simply
  publication delay. A guarded15-row trial is rejected (alley still8 versus
  NES7, whole load21 versus20). New save-only and immediate restore captures
  preserve all8,936 frames and PCM. Fresh-process/cross-ROM checkpoint tests
  were unqualified at that checkpoint; the active-loop follow-up above now
  qualifies bounded replay.1,001 unit tests passed then. No Rival/OBS changes.

- [Signed-shift load trial](SIGNED-SHIFT-LOAD-TRIAL.md): an in-place arithmetic
  replacement saves 400,880 measured shift-block master clocks and reduces
  the observed school-return loop from27 to26 frames. Executed oracle covers
  589,824 cases, including a second entry that performs256 shifts;998 unit
  tests pass. Full-route graphics regress (first scenery8/6/7 versus NES7/7/7),
  so promotion is rejected. Strict combat failures, exact frames and native
  audio remain published; no Rival/OBS changes or audible-fix claim.

- [Dispatch trial combat/menu regression](DISPATCH-COMBAT-MENU-REGRESSION.md):
  eight fresh combat captures plus four menu captures (58,098 frames). Status,
  repeated purchases, YES/NO and pause-cursor checks pass against NES oracles;
  old broken controls still fail. Sustained combat passes 1,661 SNES loops.
  Running/jumping retains the same 15/27-frame room-transition stalls; strict
  speed gate remains failed. All seven campaign outlier signatures unchanged
  from the previous cartridge; exact frames and native audio published. No
  deployment or hardware changes, no pop-free claim.

- [Direct SPC receiver dispatch trial](RECEIVER-DISPATCH-TRIAL.md): removes one
  redundant jump per unmatched poll, changing two SPC operand bytes plus
  checksum. Ten measured mall audio bridges average4.27% fewer master clocks;
  not a whole-game speedup claim. Actual packet/restart, room-entry, sampled
  four-room cadence and full renderer checks pass. All parent/trial timing and
  frame differences retained;992 tests pass. Offline candidate only; Rival
  unchanged, physical/audio-fidelity gates remain open.

- [Guarded native-PCM gameplay trial](GUARDED-NATIVE-PCM.md): both live screen
  guards pass; 2,398 complete native/common packet pairs match exactly. No
  ≥10ms exact-zero gaps in the main gameplay stretch; ending pause silence
  retained, nonzero pops not excluded. Strict command audit rejects a mixed
  pre-run SRAM export. New bounded reader requires valid, identical successive
  snapshots before future input. Video/native audio published; 990 tests pass.
  Regular cartridge restored, SNAC Yes. No ROM or audible-fix claim.

- [Hardware screen-state guard](HARDWARE-SCREEN-GUARD.md): retained an invalid
  command/PCM run where controller input navigated the OSD and restarted the
  diagnostic. New wrapper checks an audited paused screen before recording
  and again before input; live wrong-menu replay refused. Native screenshots,
  failed-run frames and receipts published; 985 tests pass. Regular cartridge
  restored at the 1P menu, SNAC Yes, OSD closed. No new audio or speed fix.

- [Current sustained-combat campaign](CURRENT-COMBAT-CAMPAIGN.md): eight fresh
  NES/SNES captures, observer-on/off timeline and PCM equality, two longer
  attack/run/jump policies. Sustained SNES combat passes1,661 loops; original
  NES has occasional three-tick loops. Running tests retain every failure,
  including a25-frame NES fade hidden behind a two-tick counter and two SNES
  room transitions. Native audio and exact outlier frames published;977 tests
  pass. No new ROM fix, physical speed verdict, or Rival/OBS changes.

- [Direct-input PCM isolates monitor sample loss](COMMON-INPUT-PCM.md): all
  1,918,403 native stereo frames exactly match OBS common float PCM. Recording
  stays aligned; the monitor branch alone loses correspondence by 1/32/1
  samples, verified by exact sequence comparison across 864,000 frames. New
  direct-input reference bypasses this downstream defect for future port tests.
  Native audio/video and all failures published; 967 tests pass. No ROM fix or
  pop-free/full-speed claim. Rival paused with SNAC Yes, same cartridge.

- [Recording-buffer accounting](OBS-RECORD-BUFFER-TRACE.md): another physical
  raw/AAC 32-sample step occurs while 2,398 source-buffer writes and 1,873 reads
  have no unexpected size changes, partial reads or unexplained mutations.
  Equal frame counts do not prove PCM fidelity; next isolate common-input PCM
  from downstream branches. Five raw silence clips and 45 rejected camera pairs
  retained. 954 tests pass; same test cartridge paused with SNAC restored Yes.

- [Same-run OBS monitor packet trace](OBS-MONITOR-PACKET-TRACE.md): reproduced
  a 32-sample raw/AAC correspondence shift while all 2,399 observed monitor
  callbacks matched input packets, with no busy-lock exits or resampler frame
  changes. This excludes those measured mechanisms for this instrumented run,
  not downstream capture faults or ROM sound defects. Six raw silence excerpts,
  16 rejected camera pairs and fixed-offset failures retained in the web review.
  946 tests pass. Same test cartridge, paused with SNAC Yes; no ROM change.

- [Five-clock candidate on Rival](WORD-PITCH-RIVAL.md): test cartridge
  `0e9ba29becef` recorded and left paused with SNAC restored Yes. Physical
  capture has failed fixed-offset audio correspondence and a failed injected
  dropout control; diagnostic branch lag changes by up to776 samples. Two
  raw gaps and six1-/six3-frame camera holds remain unexplained. All failures,
  native audio and video retained; settings unchanged.933 tests. Not a
  perceptual improvement or original-speed pass.

- [Five-clock pulse pitch update](WORD-PITCH-UPDATE.md): same-size/same-cost
  offline SPC candidate reduces mixed-byte pitch samples 40→27 (nonzero
  18→12) under the exact 1,238 hardware-recorded packets. All 50,265 executed
  cases and full 9,406-frame state/callback comparison pass. Full-game DSP
  values/order and receipt/ready clocks unchanged; 47,588 low writes move
  three clocks later. Native A/B review retains the largest residual errors.
  929 tests; not deployed or proven audibly better. Rival unchanged.

- [Exact physical-command replay](HARDWARE-PACKET-REPLAY.md): all 1,238 recorded
  packets independently received byte-for-byte by the replay engine. One
  held-out-tested offset gives 93%/93%/100% silence overlap at the three
  retained physical gaps; nearby quiet commands and DSP release writes support
  musical rests, not a confirmed hardware-cause verdict. Native audio and
  waveform review published; 925 tests pass. Remaining pops and rare slowdown
  still open. Rival unchanged; no gameplay fix or release claim.

- [Same-run physical sound-command capture](AUDIO-PACKET-HARDWARE.md): MiSTer
  seed loading and paused SRAM export now verified. The recorded episode has
  1,238 new valid records, no timeout flags and consecutive native-NMI ticks;
  repeated paused exports match exactly. Three raw audio gaps17.625/19.8125/
  11.0833ms remain. Packet-to-sample attribution is still open. Temporary
  diagnostic retired; regular build restored at1P menu with SNAC Yes.
  Seeded observer harness repaired and917 tests pass. No gameplay fix claimed.

- [Logger initialization and coverage controls](AUDIO-PACKET-STARTUP-CONTROLS.md):
  SRAM mapping and a host-preloaded header preserve the parent's full9,406-frame
  timeline/PCM exactly. Executed initialization alone reproduces the fade error;
  runtime logging still fails after removing it. Selective recording now joins
  every retained packet to actual gate events and SPC receipts, with interior
  coverage gaps explicit. No deployment or physical-audio conclusion.

- [Sound logging during acknowledgement waits](AUDIO-PACKET-INTERLEAVING.md):
  two prototypes retain exact independent SPC packet matches and steady loop/
  park cadence. Fourteen executed handshake-failure controls all flag timeouts.
  Both still fail fixed-offset fades (8/6/7 versus7/7/7), despite matching the
  parent's final short-replay image. No deployment or physical-audio verdict.

- [Lower-cost sound logging](AUDIO-PACKET-LOGGER-COST.md): word copies and a
  caller-checked reduced save set cut measured logger spans to2,846–3,166 clocks.
  Exact retained packet matching remains intact;70,000-frame word-copy endurance
  crosses the NMI counter wrap. Word-copy steady loops/park cadence pass, but
  both variants delay one room's appearance by a frame. Neither is deployed;
  the physical audio gap remains unresolved.

- [Sound-command SRAM logger qualification](AUDIO-PACKET-LOGGER.md): diagnostic
  ring wraps correctly; all4,095 retained packets match independent SPC receipts
  from a4,606-packet run. Corruption controls fail as intended. Logging adds
  3,898–4,270 master clocks plus call overhead and the parent comparison differs,
  so this is **not timing-neutral and not deployed**. Rival remains unchanged.

- [Balanced pitch build recorded on Rival](BALANCED-PITCH-RIVAL.md): cartridge
  `777635fa6d86` is now running, paused with SNAC restored Yes. Real movement/
  combat video, screenshots and native audio published. Fixed-offset raw/AAC
  agreement remains above0.9989 in all five held-out windows; no earlier branch
  shift there. A10.354ms raw gameplay silence remains unexplained, despite no
  >=10ms AAC gap in the reviewed active window. Five rejected camera pairs and
  long holds retained.887 tests; not a pop-free or full-speed certification.

- [Cycle-balanced pitch publication](BALANCED-PITCH-UPDATE.md): same-size SPC
  patch narrows pitch-write gap 17→8 clocks with unchanged cost in 50,265
  executed cases. Same-command split samples 122→51 (nonzero 37→19). Full
  9,406-frame game video/RAM and main instruction trace unchanged; room fades,
  cadence, renderer and restart gates pass. Two one-sample callback boundary
  differences remain a reported strict failure; full DAC/WAV and packet/ready
  checks establish their scope. Not deployed or pop-free.

- [Combined receiver/row build deployed on Rival](RECEIVER-POLL-RIVAL.md):
  exact tested cartridge `339d2b220a3a`, recorded hardware traversal, native
  audio and full screenshots published. SNAC restored Yes; game paused;
  saved configuration and OBS audio settings unchanged. Camera audit retains
  all 20 rejected pairs. A 17ms raw gameplay silence remains unexplained;
  a separate 32-sample recording-branch timing step explains later correlation
  mismatch but is not a sound fix. No pop-free or full-game speed claim.

- [Faster receiver polling and exact combined room loads](RECEIVER-POLL-TIMING.md):
  actual mall instruction traces isolate increased paired-byte waits, not SPC
  ready waiting.20-byte cartridge experiment preserves continuous sweep clocks
  under delayed packets and8,353 actual game packets. Combined with the verified
  compact converter, all three room-entry and40-offset fade gates pass:7/7/7
  first scenery,19/28/29 total loads. Fresh combined3,823-loop cadence and
  full renderer pass, plus1,638 actual DSP restart orderings.874 tests;
  physical audio and broader original-speed proof remain open. No Rival restart.

- [Split-byte pulse pitch investigation](PULSE-PITCH-WRITES.md): all3,482,203
  actual pulse samples reconstructed from DSP byte-write timing. Experimental
  prefetch reduces nonzero intermediate-pitch samples33→19;4,096 executed
  final-state cases pass, but active publication costs18 extra clocks per
  voice. All402 eligible note starts remain correct. Native A/B audio and
  plots published;869 tests. Not an audible-pop fix or game release; Rival
  unchanged, physical audio and graphics/fade regressions remain open.

- [Beam-bounded hidden rows and original fade schedule](HIDDEN-ROW-DEADLINE.md):
  fresh neutral NES/SNES traces identify late second fade service in Compact12.
  Three real scanline-cutoff prototypes tested.128 makes alley/park fades exact
  but mall early and alley rendering-off duration late;96/112 also fail. All
  results and original screenshots published.862 unit tests; prototypes remain
  unqualified, no promotion or Rival restart.

- [Compact hidden-row indices](HIDDEN-COMPACT-INDEX.md): 6,144 executed VRAM
  cases and five rejected mutants; exact game-patch/oracle binding. Eight paired
  batches save 3,930–4,780 clocks; actual early alley row phases shrink7,130
  each. Fresh 3,550-loop cadence and renderer checks pass, but both16/12-row
  variants still fail initial alley visibility.856 unit tests; no promotion
  or Rival restart. Full-game speed and physical audio remain open.

- [Alley-load interrupt profile and budget trials](ALLEY-LOAD-BUDGET.md):
  current alley visibility is22 frames versus NES20. Eight rows fixes its
  fade but regresses mall/park; twelve improves later colors but still fails
  first visibility. Both rejected. Neutral full instruction replay identifies
  ~120,000-clock hidden row phases; web collages retain failures. Current
  renderer passes7,238 eligible frames without splits/stale holds. Rival unchanged.

- [Short-silence command/filter attribution](SHORT-REPLAY-SILENCE.md): all210
  ≥5ms same-command replay gaps retained; at most0.625ms per gap outside a
  packet-commanded quiet state. All548 fully silent SNES callbacks have constant
  NES prefilter input; boundary differences retained.842 tests, including10ms
  dropout controls. Physical gameplay gaps remain unresolved; no new ROM/reset.

- [Actual DSP pulse-start repair and Rival trial](PULSE-ONSET-RIVAL.md):
  identical-command stale-pitch nonzero onsets27→0, with neutral observer and
  negative controls. Candidate passes3,550 stable two-tick loops and is deployed
  as `fa882cb61138`. Raw/OBS hardware audio held-out correlations exceed0.9986;
  two short silences remain unresolved. SNAC restored, game paused. No claim
  of all-pops resolution or full-game original-speed equivalence.

- [Pulse-1 sweep arithmetic correction](PULSE-SWEEP-ARITHMETIC.md):
  actual legacy-engine bug fixed behind a default-off flag. All 28,560 executed
  SPC target cases now match with identical instruction timing; three mutants
  caught. Game candidate passes 8,950 received packets and 3,825 stable two-tick
  loops; no short irregular park holds. Same-window packet timing differences
  retained. 767 tests. Not deployed; sweep-divider timing and combat sputter open.

- [Isolated cursor audio regression](ISOLATED-CURSOR-AUDIO.md): eight real Rival
  cues and cursor movements verified; five actual-recording audio mutations and
  two actual-frame arrow mutations caught. 760 tests. Narrow menu-sound check,
  not a combat-audio pass; SNAC restored, game paused, no restart.

- [Actual pre-mute hardware audio capture](RAW-HARDWARE-AUDIO-CAPTURE.md):
  fixed a self-test blind spot: OS monitoring was muted despite OBS input being
  unmuted. Raw debug capture works without unmuting speakers. A new 143ms AAC
  gap is also 179ms raw silence during a room transition; old combat gaps remain
  open. Fixed-offset mismatch, negative capture, and AAC-only dropout mutant
  retained. 745 tests; SNAC restored, paused by Trash Pick-Up. No ROM change/reset.

- [Full-route original-NES camera latency](FULL-ROUTE-CAMERA-LATENCY.md):
  957 NES and 930 SNES changed stores, none missing on display. NES has 92
  same-frame stores, but mall loop-start-to-display is one frame for all 146
  SNES changes versus one or two on NES; store delay alone is misleading.
  Eight actual-route synthetic delay/drop controls caught; 732 tests. No ROM
  change or Rival restart. Physical audio/scrolling and strict gate remain open.

- [Actual camera-store to display latency](ACTUAL-CAMERA-STORE-LATENCY.md):
  all 930 qualified SNES changes across four rooms appear next frame, none
  missing. Original NES park reference has 392 next-frame and three same-frame
  changes; differences retained. Full observer timeline/PCM neutral, unchanged
  source-frame strips published. 721 tests; strict publication gate still
  fails, physical audio gaps still open. No ROM change or Rival restart.

- [Current four-room cadence and exact backgrounds](CURRENT-FOUR-ROOM-CADENCE.md):
  all3,588 stable SNES iterations take two ticks; original NES has13 three-tick
  loops in its differing encounters.800 backgrounds match exactly, with
  259/103/110/328 common positions and settling no later than NES. Only the old
  same-frame publication gate fails (885 observations); no waiver.704 tests;
  no ROM change or Rival input/restart.

- [Physical combat audio: held-out music-context candidates](PHYSICAL-AUDIO-CONTEXT.md):
  repeated music matches before/after the three longer gaps at fixed offsets;
  nearby reference rests have measured mute/onset commands. Two nearly tied
  candidates and mismatched gap durations retained, so hardware gaps remain
  unresolved.696 tests; no ROM change, controller input or restart.

- [NES reference filter tails versus missing notes](NES-FILTER-TAILS.md):
  all7,144,636 filter outputs independently reconstructed; observer timeline,
  RAM and WAV exactly neutral.245 active-reference callbacks have constant
  pre-filter input; the other12 are precisely the measured callback-boundary
  cases. Explains this short-gap evidence, not overall synthesis fidelity or
  the three physical combat gaps.690 tests; no ROM change or Rival restart.

- [Actual SPC→DSP→DAC latency and callback-boundary audit](DSP-CALLBACK-LATENCY.md):
  full8,934-frame observer is timeline/WAV neutral;4,762,867 raw DAC samples equal
  delivered PCM. Frame6580's packet arrives after its labeled audio callback,
  with sound360 SPC cycles later.12 of256 short-gap contexts cross this boundary;
  244 remained separately unresolved at that stage, as do three physical combat gaps.683 tests;
  no ROM change, Rival input, restart or release claim.

- [Physical triangle build follow-up and NES-reference silence regression](PHYSICAL-TRIANGLE-REVIEW.md):
  actual street combat followed by ten seconds of exact digital pause silence;
  SNAC restored Yes, game paused outside Cross-Town High. Three147–151ms combat
  gaps remain unclassified. One four-frame scenery hold includes actor movement;
  one one-frame interval unresolved.38,334-write NES replay finds no sustained
  guarded-silence mismatch, retains257 shorter active callbacks and detects all
  four injected dropouts.673 tests; no further ROM change/restart or release claim.

- [Current Rival test build 071c89e: triangle attack/release](TRIANGLE-GAME-RIVAL.md):
  deployed September 18 at 09:54:51 UTC. Same-command game comparison reduces
  worst triangle boundary step 2,266→197; one triangle and twelve full-mix
  boundaries worsen, all retained. 666 tests; park main loop stays at two ticks,
  no late NMI intervals, actual SPC transport and guarded silence pass. Physical
  menu audio recorded and analyzed; gameplay pops and full-game speed still open.

- [Triangle note-boundary prototype, not deployed](TRIANGLE-BOUNDARY-EXPERIMENT.md):
  eight phase-varied SPC/NES probes expose release-only restart regressions.
  Attack+release lowers worst selected step1,872→253, with~0.74% steady-level
  difference; four small per-event increases remain failures. Game mix, short
  notes, packet budget and hardware unqualified.659 tests; Rival unchanged.

- [Camera hold origin: commands versus missing work](CAMERA-HOLD-ORIGIN.md):
  original NES four-frame hold has regular two-frame main starts and a repeated
  camera command. Exact Rival frame collages show actor movement during the
  first flagged hold; second remains unresolved. Six negative/positive control
  tests added,652 total pass. No physical-event waiver, ROM change or restart.

- [Actual Rival park sweep and combat recording](PHYSICAL-PARK-REVIEW.md):
  reached park, recorded surviving sweep and subsequent death/respawn sequence;
  SNAC restored Yes, game paused by Trash Pick-Up. Scenery tracking measures95
  two-frame holds, two four-frame holds and10 ambiguous pairs (all retained).
  Audio unmodified, no clipping, not pop-free certified.646 tests, no ROM change.

- [Musical rests versus held-voice dropout regression](GAME-SILENCE-SOURCE.md):
  full-mix40,222-write NES replay;4,868 guarded held-voice frames with no≥10ms
  silence, four injected menu/street/shop/park failures caught. All714 observed
  gaps retained; nearby mute commands do not become a causal/pop-free pass.
  639 tests. No ROM change/restart; physical short-gap correlation still open.

- [Current Rival test build840de24: timing plus noise correction](MAIN-PHASE-NOISE-RIVAL.md).
  Restarted18:57:58 UTC September17; remote hash,1P menu and physical audio
  handoff verified.1,003 stable park loops all use exactly two ticks; zero late
  NMI/packet intervals or short scrolling hitches on the tested route. Noise
  spectrum closer to NES, no non-noise/gameplay changes. Physical follow-up:
  30s combat captured,20s paused exactly silent, SNAC restored Yes, game paused
  by Trash Pick-Up. Strongest-step/silence clips published; shorter audio gaps
  remain unclassified. Second-lap endurance dies and respawns, not a speed pass.
  Expanded
  alley coverage211 exact positions; longer original NES route times out.
  Full-game/input-latency, strict publication and gameplay-pop claims remain open.

- [Stable main-phase scheduling](MAIN-PHASE-SCHEDULING.md): branded candidate783
  eliminates short irregular holds in both park directions and passes every
  fixed-offset room fade, short movement, status and repeat-shop checks.
  Actual SPC transport and PCM bounds pass, not a pop-free verdict. Background
  room1 coverage and strict publication gates remain open. New NES/store/render
  timing join retains same-frame exceptions; no full-game speed claim or Rival
  restart. User authorizes meaningful tested restarts without another prompt.

- [Column-fetch optimization, not promoted](COLUMN-FETCH-OPTIMIZATION.md):
  5,120 executed original/optimized pairs and six rejected mutants; common
  twenty-row fetch about35% faster. All73 old runtime symbols remain fixed.
  Full-route motion is mixed/worse despite clean renderer coverage. A bound
  seven-frame collage proves3/1 producer and display intervals.594 tests pass;
  default-off, no Rival restart or audio-fix claim. Target joint frame budget.

- [Retained-graphics deadline guard rejected for promotion](SECOND-TICK-DEADLINE-EXPERIMENT.md):
  36 actual-beam/NMI cases and four mutants pass; old missed-interrupt control
  reproduced. Full-route branded short irregular holds regress from6/7 to12/25.
  Neutral CPU trace now observes every VBlank, but one actor/main iteration
  crosses into the next frame, producing3/1 camera spacing.588 tests pass.
  Default-off, no Rival restart. Next: budget main work and producer fallback
  together, retaining complete generation/latency checks.

- [Combined early-main experiment](EARLY-MAIN-COMBINATION.md): unbranded735
  has zero short irregular scrolling holds on the measured route; branded744
  passes three first-visible load-latency gates but retains six/seven isolated
  three-frame holds. Actual instructions prove one retained graphics pass
  masks an entire VBlank, losing a tick. Stronger cadence and trace-window
  validation added; 586 tests pass. Background/fade qualification incomplete;
  no Rival restart or pop-free claim. Next: deadline-aware producer service.

- [Cached-pad polling optimization, not promoted](JOYPAD-POLL-OPTIMIZATION.md):
  replaces sixteen generic reads of already-latched pads; 65,536 matched pad
  pairs, five rejected mutants and both nonzero live ports tested. Poll loop
  saves about19,794 master clocks; all68 existing runtime symbols preserved.
  Full renderer coverage passes, but east/west jitter is24/20 versus11/18.
  Combining fused sprite positioning gives20/6; first load remains late.
  578 tests pass. Default-off; no Rival restart, mapping or sound change.

- [Fused sprite positioning, not promoted](SPRITE-POSITION-OPTIMIZATION.md):
  65,536 executed offset pairs and six rejected mutants; the complete signed
  offset/addition block is about one-third faster in 8,192 matched cases.
  Only 488 ROM bytes differ and all 68 prior runtime symbols stay fixed.
  Full-route scrolling remains mixed (east21/west15 versus parent11/18),
  first load is one frame late, and fade coverage fails.570 tests pass;
  default-off, no Rival restart or audio-fix claim.

- [Second-tick producer deferral rejected](SECOND-TICK-PREPARE-EXPERIMENT.md):
  102 executed guard/service cases and five mutants pass; actual game starts
  earlier but east/west scrolling jitter worsens to31/19 pairs versus11/18.
  Full 8,593-frame renderer replay is neutral.564 tests, default-off, no Rival
  restart. Next target: reduce sprite-building work rather than shift it.

- [Noise correction qualified against the game](NOISE-GAME-CORRECTION.md):
  optional ten-byte SPC table correction, all 8,934 non-audio frames identical,
  8,481 identical packet/processing traces, non-noise PCM sample-identical.
  382 register-selected noise frames move closer to the same-write NES replay.
  Fixed a post-load channel-isolation harness bug. Not a speed/pop-free pass;
  original-speed gate still open, Rival unchanged.

- [Noise-channel experiment](NOISE-CHANNEL-EXPERIMENT.md): executed NES/SPC
  coverage for all 16 rates, mute/restart/volume. A diagnostic-only ten-byte
  clock-table correction improves measured spectral centroids at all changed
  rates. SNES gates pass; combined report retains NES filtered mute-tail FAIL.
  557 tests; not integrated into game, no Rival restart or gameplay-pop claim.

- [Sprite-coordinate loop optimization](SPRITE-COORDINATE-OPTIMIZATION.md):
  all65,536 matched input pairs/six mutants; exact small loop about28% faster
  in8192 timing cases. Preserves old runtime layout; only295 ROM bytes differ.
  Park return jitter improves, outward jitter does not; first load remains
  one frame late and one fade frame lacks renderer coverage.818 exact selected
  backgrounds, status/movement pass.553 tests; default-off, Rival unchanged.

- [Row-phase scheduling tested and rejected](VISIBLE-ROW-PHASE-EXPERIMENT.md):
  300 executed cases/six mutants prove guarded4/0-row mechanics, but full-route
  camera jitter worsens, one logical-position background check fails, renderer
  coverage is missing at one fade frame, and first load is one frame late.
  New failure diagnostics retain incomplete coverage instead of hiding later
  faults.550 tests; default-off, live ROM unchanged, no restart or audio fix.

- [Visible-row cache tested, not promoted](VISIBLE-ATTRIBUTE-CACHE.md):
  384 executed cases/all256 attributes/six rejected mutants. Adjacent-row
  preparation about14% faster, cold cases slightly slower. Full route remains
  split/stale-hold free,773 exact backgrounds; actual camera1/3 jitter is not
  improved. Default-off, disabled build byte-identical to608. No Rival restart.

- [Actual camera presentation jitter confirmed](DISPLAY-PACING-CURRENT.md):
  original NES park return has zero1/3-frame holds; the Rival ROM has26/25.
  Fresh instruction+renderer counterexample shows producer intervals2/2 but
  displayed intervals1/3. Every pixel group/line is checked; long stops and
  blank boundaries retained. Fixed regression deliberately FAILS.541 tests;
  no runtime change, restart or audio fix. Target producer/interrupt timing.

- [One-scanline camera experiment, not promoted](CAMERA-LINE30-EXPERIMENT.md):
  123 actual-beam cases/six mutants; zero splits and stale holds,780 exact
  backgrounds. Earlier publication helps one captured frame but timing shifts
  delay another. Default-off; disabled build byte-identical to608. Actual
  rendered cadence is the next investigation. No Rival restart or audio fix.

- [Physical gameplay and paused-audio capture](HARDWARE-GAMEPLAY-AUDIO-CURRENT.md):
  bounded real-Rival input drives street combat and rightward scrolling;
  30 seconds of gameplay audio plus 20 seconds of exactly silent paused PCM.
  Dead-capture and paused-click controls rejected. Video, screenshots and
  timestamped inputs retained. Runtime SNAC restored to Yes, OSD closed,
  game paused. Same34835f8 ROM; no restart or pop-free/full-speed claim.

- [Physical menu dropout and complete-route sound evidence](HARDWARE-MENU-AUDIO-CURRENT.md):
  actual Rival/OBS menu compared with same-ROM no-input PCM using four-second
  calibration and24-second independent holdout; no large missing-energy bins,
  four executed dropout/clock-slip controls rejected. Full route has no
  clipping/missing callbacks; strongest transitions retained for listening.
  Six long delivery-gap interiors are silent.523 tests. No new ROM/restart;
  smaller clicks, gameplay acoustics and full-game speed remain unverified.

- [Stationary-camera interrupt scheduling and Rival restart](STATIC-CAMERA-ARM-CURRENT.md):
  candidate616 (`34835f8`) is on Rival. Whole loads20/28/29 versus NES20/31/30;
  park camera calculations average two frames, short movement no later.
  Zero renderer splits or extra-frame held cameras,774 exact background
  samples, repeat shops and Present Status pass.212,405 received sound bytes
  checked; actual OBS restart audio passes12 ident pitch checkpoints and
  resumes game music.516 tests. Full-game speed, intermittent gameplay pops,
  fade/latency gates and controller presets remain open.

- [Full-route held-camera and execution cadence checks](CAMERA-CADENCE-CURRENT.md):
  zero stale holds across6,384 unchanged-camera frames; real old failure is
  detected. Fresh NES/SNES camera traces average about two frames/update in
  both park sweeps, with differing jitter. Short rightward movement passes.
  Three-port combination rejected for21-frame loading.507 tests. Neutral
  CPU trace identifies stationary-camera interrupt scheduling as next target;
  no new deployment, full-game speed or acoustic pass.

- [NES-speed first load and skipped camera commit](CHR-POINTER-VBLANK-CURRENT.md):
  persistent CHR pointer reduces first loading to20 frames, matching NES.
  Early VBlank camera commit fixes an actual extra-frame park lag when the
  final graphics batch is refused.775 exact backgrounds, zero splits across
  7,314 frames, both status entries exact and212,405 received sound bytes
  verified.256 adapter cartridges, nine publisher cases/four mutants and500
  tests pass. Fade/latency/acoustic gates remain open; no Rival restart.

- [Compact sprite-generation marking and phase experiment](PUBLISHER-GENERATION-CURRENT.md):
  fixes generation-gated build overflow, preserves pending uploads and caller
  state;27 executed cases/five mutants plus36 beam cases/four mutants pass.
  Combined run has zero splits across7,489 frames and212,336 actual sound
  bytes verified, but loads22 frames versus retained21/NES20.499 tests; opt-in
  only, no promotion/restart. The phase wait is not the dominant sampled cost.

- [Three-port transport measured, not promoted](TRIPLE-TRANSFER-CURRENT.md):
  data-transfer phase27.8% shorter; new isolated observer checks all209,139
  actual received bytes plus padding across9,093 game packets. Three physical
  wrong-port mutants rejected;496 tests pass. Loading worsens to22frames
  and full-route renderer coverage fails at2119. Candidate539 remains the
  comparison build; no Rival restart or acoustic fidelity claim.

- [Cheaper guarded CHR pointer setup](CHR-LOW-POINTER-CURRENT.md): removes
  384 generic pointer calls in the measured first load;256 executed adapter
  cartridges and reader/cache mutants pass. Zero splits across7,235 actual
  rendered gameplay frames,784 exact background samples, both status entries
  exact and9,233 verified SPC packets.492 tests pass. Loading remains21 versus
  NES20; no acoustic pass or Rival restart. Adjacent-row combination rejected.

- [Current tear-free load profile](CAMERA-SAFE-LOAD-PROFILE.md): neutral
  9,409-frame replay separates original frame waits from decode work and
  ordinary NMI interruptions. About65% of the first actor call's elapsed
  cost is interrupt work. No speed patch or Rival restart;21 versus NES20
  remains a failure. New fail-closed original-wait attribution tests.

- [Late-camera tearing prevented](CAMERA-SAFE-PUBLICATION.md): new guarded
  live-table publication changes actual full-route split counts from729/7235
  eligible frames to0/7234.42 real-beam cases, full-hook NMI tests and488
  Python tests pass. Loading remains21 versus NES20; publication/settling
  and acoustic gates remain open. No Rival restart or full-speed claim.

- [Live-half OAM optimization, not promoted](OAM-LIVE-HALF-EXPERIMENT.md):
  full initialization then256 live bytes;512 executed full-OAM readbacks,
  four rejected mutants and complete pixel fixture pass. Actual DMA intervals
  shrink, but first-room loading returns to22 frames and scrolling/coverage
  still fail.9232 audio packets verified; no acoustic pass or Rival restart.
  483 Python tests pass.

- [21-frame load, rejected scrolling](HIDDEN16-WORD-CURRENT.md): combining
  hidden16 and word fills saves one room-load frame (NES20), but a fresh
  neutral renderer trace proves an old/new-camera split followed by a lagged
  frame. All 784 stable background samples and both status entries match;
  these do not override the failure. Camera hook arrives at line38. No
  promotion/restart; 481 tests pass.

- [Recorded-delivery audio comparison](PUBLICATION-AUDIO-REPLAY.md): all
  39,454 writes replayed with actual packet-frame boundaries; the two suspect
  silent-frame discrepancies shrink by 39x/20x RMS. This supports a probe
  scheduling artifact, not a dropped-note diagnosis. No sound patch; acoustic
  fidelity still open. 479 tests pass.

- [Full-route shared audio stimulus](FULL-ROUTE-AUDIO-STIMULUS.md): the NES
  probe now executes all 39,454 writes across 9,408 frames and five bank
  crossings, rejecting three broken ROMs. Matched park clips expose a
  timing limitation: early mute and late next-note writes within one host
  frame are batched together by the probe. Silence differences therefore
  do not yet prove a sound-engine fault. 477 tests pass; no game patch/restart.

- [Current same-stimulus audio diagnosis](CURRENT-AUDIO-STIMULUS-REPLAY.md):
  fresh 9,408-frame PCM is bound to all 9,055 SPC packets and 999 key-on events;
  no callback, transport, clipping or existing digital-bound failure. An
  asset-free NES replay executes all 13,310 captured APU writes through frame
  3,224 and rejects physically silent and empty-frame-bug control ROMs. The
  strongest transition is large on NES too. This is not cycle-equivalent or
  full-route acoustic certification, and no audio patch/restart was made.

- [Larger hidden batch, not advancing](HIDDEN16-CURRENT-EXPERIMENT.md): all
  three rooms now match NES fade images/timing, but first whole load remains
  22 versus 20 and fresh scrolling fails alley coverage plus a publication
  warning. 4,096 actual-VRAM cases and four mutants pass; status and scoped
  audio delivery pass. Neither helper success nor fade parity overrides the
  remaining failures. Baseline stays at the 12-row paired-read candidate.

- [Fixed-frame settling diagnosis](CAMERA-WORKING-STATE-DIAGNOSIS.md): the
  lone remaining 1,259-frame settling value samples an interrupted working
  camera calculation, not a rendered camera change. Actual renderer lines,
  committed state and neutral CPU trace establish this without changing the
  old failed gate. 459 unit tests pass. New load profiling identifies hidden
  background upload work; scalar rectangle fills do not improve loading.

- [Current paired CHR source reads](CHR-READ-PAIR-CURRENT.md) save another
  first-room frame: 22 versus NES 20. 256 executable cartridges, cache and
  paired-read negative controls, and 455 unit tests pass. All 849 sampled
  backgrounds match, no late scroll publications, both status entries pass.
  First-room visibility, strict settling and acoustic acceptance remain open;
  no Rival deployment. A preliminary word-fill combination does not improve
  room 1 further and has not inherited the full qualification.

- Latest scoped optimization: [CHR read-pointer cache](CHR-READ-CACHE.md)
  reduces the first whole-room load from 24 to 23 frames (NES 20), with
  128 executed adapter cartridges and six rejected mutants. All 753 sampled
  backgrounds and both Present Status entries match; no late publications
  occur in the new sweep. First-room visibility and strict settling still
  fail. Packet cadence passes but acoustic fidelity remains unverified.
  Default-off; no Rival restart or deployment. 454 Python tests pass.

- [Present Status fields blank (#4)](https://github.com/struktured-labs/river-city-ransom-snes/issues/4):
  [fixed and deployed for hardware confirmation](PRESENT-STATUS-REGRESSION.md).
  Three missing PPU-register translations; original NES pixels, repeated entry,
  game-state values and unchanged park execution are verified automatically.
- [Rare park slowdown](PARK-ENTRANCE-SLOWDOWN-REGRESSION.md): physical OBS
  candidates retained; input-only SNES replay now demonstrates irregular SPC
  packet delivery outside transitions. Historical candidates failed timing;
  the newest scoped result is linked below.
  [Exact-clock stage profile](PARK-STAGE-COSTS.md) now reproduces missed NMI
  deadlines with observer-equivalent video/audio; smaller sprite comparison
  experiment reduces late packets but is not yet eligible for deployment.
  [Field-pair sprite conversion](SPRITE-PAIR-EXPERIMENT.md) further reduces late
  packets to 12 and passes shop/status checks, but still misses deadlines and
  closes the pause menu one frame later than the original.
  [PPU-ring profiling and interrupt guard](PARK-RING-INTERRUPT-EXPERIMENT.md)
  isolates the next cost center and fixes experimental interrupt ownership.
  Corrected combined candidate still has six late packets; shop traversal
  needs state-aware checkpoints before its menu tests are meaningful.
  [Waypoint café harness](WAYPOINT-SHOP-HARNESS.md) now resolves that test
  prerequisite: repeat purchases and YES/NO pass on the corrected candidate,
  while the old stale-cursor ROM is rejected after verified café arrival.
  [Native OAM word-copy candidate](OAM-WORD-COPY-VALIDATION.md) now passes the
  park packet and profiled interrupt deadlines, with observer-neutral full
  video/audio replay. Movement, café and status gates pass. Full-game speed,
  physical audio fidelity and the one-frame pause-close discrepancy remain open.
- [Room-entry timing and dense scrolling](ROOM-ENTRY-TIMING.md): direct NES
  PPU telemetry is observer-neutral. The live port shows the first room pixels
  29–30 frames after rendering-enable versus NES 7. An opt-in hidden-load
  producer budget reduces this to 11–12 and passes scoped gameplay/menu/audio
  cadence checks, but still fails the original visibility/fade target; not
  deployed. Dense alley coverage and early pause-animation parity also remain
  incomplete. Rejected variants and actual broken-scrolling controls are retained.
  [Mirrored-row native-word copy](ALIAS-WORD-COPY-EXPERIMENT.md) saves 248
  clocks in a controlled FastROM helper test, with 160 executed correctness
  cases and three rejected mutants. A twelve-row combination reaches 11/11/11
  frames and passes stable park packet timing, but remains below the original
  timing standard and is not deployed.
  [Load interrupt starvation](ROOM-LOAD-INTERRUPT-STARVATION.md) adds whole-load
  timing gates and real-DMA mutation tests. Larger hidden transfers retire rows
  earlier without improving visibility. A neutral instruction trace shows
  93% of the long first sprite-list call is NMI work: main-thread starvation,
  not the sprite routine itself, is the next measured target.
  [Fused/unrolled row conversion](FUSED-ROW-CONVERSION.md) removes the extra
  dirty-alias copy and per-tile index bookkeeping. 1,856 snapshot cases and
  three mutants pass; a ten-row candidate passes scoped park/movement/status
  checks and neutral replay, but 11/10/11-frame visibility still fails NES
  7/7/7. No deployment or full audio-fidelity claim.
  [Row publication experiments](ROW-PUBLICATION-EXPERIMENTS.md): split-plane
  staging passes broad functional tests but is not advancing after a park
  packet failure. Hidden-only contiguous runs save 14,316–28,258 clocks in
  equal-output DMA tests and pass park timing, yet visibility remains 11/10/11.
  Neither is deployed; palette scheduling and main-loop latency remain open.
  [Palette pipeline trace](PALETTE-PIPELINE-TIMING.md) now separates 2–3 extra
  frames before fade generation from one extra generation-to-visible frame.
  [FastROM consumer entry](FAST-PUBLISHER-EXPERIMENT.md) saves CPU clocks and
  one room-entry frame, but fails four park packet deadlines; not deployed.
  [Direct hidden-row uploads](HIDDEN-DIRECT-ROWS.md) reduce scenery arrival to
  9/7/9 with 1,856 actual-VRAM cases and four mutants, but expose 22 park gaps.
  A [camera completion lost-NMI race](CAMERA-NMI-LOST-EDGE.md) is now reproduced
  at the VBlank boundary and fixed in an opt-in build. Eleven paired edge
  cases pass; full replay still has 15 over-limit packet intervals. Neither
  change is deployed or a whole-game speed/audio completion claim.
  [Retained-NMI early sound and late graphics guard](EARLY-AUDIO-LATE-PREPARE.md)
  now remove all over-limit stable park packet intervals in the full replay.
  Status and short movement match NES; complete audio, key-on packet fields
  and observer neutrality are checked. Digital transient bounds pass, not a
  physical or subjective no-pop verdict. Room scenery remains 9/8/9 versus
  NES 7/7/7, and dense alley coverage is 63/64 required samples. Not deployed.
  [Compact hidden-row lookup](HIDDEN-HIGH-LOOKUP.md) saves 1,634 clocks per
  measured direct row, with 1,856 actual-VRAM cases and six rejected mutants.
  Its combined FastROM/early-audio build passes park packet timing but still
  loads at 9/8/9 and has insufficient park camera coverage (20/64). A refreshed
  neutral trace identifies a 58,096-clock palette-copy loop and distinguishes
  remaining generation delay from the extra display frame. No deployment.
  [Guarded original palette-copy hook](GUARDED-PALETTE-COPY.md) now reduces
  four observed game copies to 2,730 clocks each. All 59 paired cases, five
  mutants and exact guarded-path/timing checks pass. Park cadence, status and
  short movement remain passing, but room visibility remains 9/8/9 and park
  scrolling coverage is still insufficient. Publication order is the next
  target; no hardware deployment or full audio-fidelity claim.
  [Eligible pending-palette publication](PENDING-PALETTE-PUBLICATION.md) now
  makes room 2 exact at all 40 fixed fade offsets. The queue-guarded candidate
  reaches 9/7/9 first scenery and passes park packet timing, status and
  same-NMI palette-source checks. 55 CGRAM/ABI cases and six mutants pass.
  The improved post-fade scenery sweep rejects a real broken-scrolling ROM,
  but latest park coverage is still only 21/64. Rooms 1/3 and full acceptance
  remain open; the earlier 8/7/8 unguarded prototype is not advancing.
  [Park waypoint coverage](PARK-WAYPOINT-COVERAGE.md) identifies death then
  a mall pause menu behind the old 21-position coverage shortfall. A new
  bounded input-only sweep covers 296 common park positions (748 total),
  with full observer neutrality and 8,789 verified audio packets. The image
  gate retains 15 jump-sprite overlaps; the separate four-cycle endurance
  run still fails after death. No pixel masking, lowered coverage threshold,
  same-input speed claim, or deployment. 420 Python tests pass.
  [Independent background observation](BACKGROUND-SCROLL-OBSERVATION.md)
  now verifies all 748 sampled positions, including 296 in the park, in
  both the original strip and expanded y=32..191 playfield. Original
  screenshots retain the 15 actor overlaps. 80 actual-renderer qualification
  cases pass; the real broken-scrolling control fails 16 backgrounds and
  999 publications with adequate coverage. Full primary video/state/PCM
  neutrality holds on NES and SNES. 423 unit tests pass. Remaining loading,
  combat speed and acoustic acceptance are unchanged; no deployment.
  [Initial WRITE-head palette publication](INITIAL-WRITE-HEAD-PALETTE.md)
  reduces first scenery to 8/7/8 while retaining room 2's exact fade. The
  broader later-generation preview regressed room 2 and was rejected.
  343 executed caller/CGRAM cases, four unsafe mutations and an actual
  consumer-budget regression protect the new ordering rule. Fresh tests of
  this exact candidate pass all 748 background positions, Present Status,
  short movement and stable park packet cadence; 426 unit tests pass.
  Loading still fails NES 7/7/7. Refreshed parent-ROM instruction profiles
  put 64–66% of the first game-update call inside graphics/audio interrupts.
  No hardware restart or complete acoustic/full-game-speed claim.
  [Invocation-local hidden attribute cache](HIDDEN-HIGH-CACHE.md) passes
  4,096 actual-VRAM cases and four unsafe mutants; paired batches save
  12,130–15,626 clocks. A twelve-row combination makes all 40 park-entry
  fade checkpoints exact and saves one whole loading frame there, but room
  1 remains late and room 2's later fade steps regress. Ten/fourteen/sixteen
  row alternatives also retain failing timing evidence. All four pass scoped
  stable park packet cadence. Cache remains opt-in; no deployment. 428 unit
  tests pass. Original generation/publication phase is the next target.
  Fresh cached-twelve integration passes 789 background positions (348 in
  the park), full observer/normal neutrality and both Present Status entries.
  Those passes do not waive the retained room-1/2 fade failures.
  [Cached-row palette phase](CACHED-PALETTE-PHASE.md): safely previewing all
  write-head fade generations restores room 2's exact forty-frame fade.
  Same-NMI source correlation covers all four original copies; both policy
  modes pass 343 executed cases and four mutants. Fresh 789-position scenery,
  status and park packet checks pass; 429 unit tests pass. Room 1 remains late,
  and park colors at two offsets are early. The current trace pinpoints a
  244,298-clock interrupt just before first fade initialization. No deployment.
  [Guarded hidden sprite deferral](HIDDEN-SPRITE-DEFERRAL.md) passes 106
  executed OAM/publisher cases and five rejected mutants. Three observed
  hidden sprite stages shrink to 306 clocks. Room 2/3 fades become exact;
  room 1 remains one frame late per step. Fresh background testing FAILS at
  two park positions, and the return route times out after death/respawn.
  Those failures block promotion despite passing status/packet tests.
  The next CPU target is the second game iteration after rendering-enable,
  not the now-on-time first fade initialization. 431 unit tests pass.
  [Actual renderer deadline diagnosis](RENDERED-SCROLL-DEADLINE.md) confirms
  both scrolling failures: camera hooks arrive at lines 35/47, after the
  line-32 street deadline; old scroll persists through line 158. NES is
  correct throughout. Three complete observer/normal comparisons preserve
  all timeline fields and PCM (the SNES route still times out). The previous
  frame-end publication check missed these real errors. 435 tests pass;
  no graphics/timing gate changes, candidate promotion or Rival restart.
  [Direct dynamic APU writes](DIRECT-APU-WRITES.md) remove duplicate dispatch
  work: 6,144 paired executable cases, five rejected mutants and 80 exact-clock
  samples validate 466–1,110-clock savings per accelerated write. 438 unit
  tests pass. Fresh 700-position scrolling still fails at two different
  positions; first-room loading and the death/respawn route timeout also
  fail. 9,222 packets and scoped park cadence pass; no acoustic certification,
  deployment or restart. The option remains default-off.
  [Direct bank restoration](DIRECT-BANK-RESTORE.md) saves 6,016–6,288 clocks
  per measured call; 16,896 executable comparisons, 512 real pending-edge
  cases within that matrix, and seven mutants validate the helper. The fresh
  controller-only sweep now completes in 8,807 frames; 753 common positions
  retain one actual line-38 camera miss plus a separate boundary warning.
  Room-1 fade differences shrink to offset 7 only, but first scenery/whole
  load remain late. 9,223 packets, scoped park cadence and status pass.
  441 unit tests pass; full speed/acoustic acceptance and deployment remain open.
