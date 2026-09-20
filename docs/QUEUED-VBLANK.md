# Real-event VBlank queue

The exact saved-state stall at frame2239 is recovered by candidate2916:
`build/queued-vblank-urgent-fusion-trial-2916/native-cpu.sfc`, SHA
`01e8bb8d1f8cdcdcb85b1321856d97167f2ca4634bf73659fae25f4cb470d15b`.
This is an offline experiment, not a release or original-NES-speed certificate.
Rival remains on harmonic splash2648; nothing was uploaded or restarted.

[Replay collage, menus and native audio](http://127.0.0.1:8766/queued-vblank-review-2943/)
authenticates4279 source files,15 artifacts and two exact unnormalized WAVs.
The page was inspected in Chromium. It retains all four failed simpler
compositions as well as the combined candidate's remaining combat failure.

## Mechanism and safety boundary

Earlier restore-local instruction traces proved that `$4210` expires during a
long masked original interrupt. Reenabling NMI after the frame boundary cannot
recover that event. The new collector reads and acknowledges the actual flag
during graphics-ring work, records pending service, and leaves the active
native/audio event identity unchanged. The old interrupt completes its sound
publication before the return tail services a collected event using the same
original interrupt frame. The queued native entry skips a second flag read.
This does not synthesize ticks or allow reentrant original game interrupts.

The helper occupies `$7200..73FF` in eight code-bank mirrors. WRAM
`$1B87..1B8C` contains pending/collected/served counters and an overflow fault.
Saved-state admission requires these new bytes to be zero; no guest memory is
fixed up after restore. Collection requires depth1, the original gameplay task,
and original PPU NMI enable. Active-display probes use nonacknowledging `$4212`.
A guard prioritizes queued service over retained graphics preparation without
consuming the preparation's ownership.

## Executed qualification

- Queue oracle2921:130 cases with real MMIO flags, all caller registers/stack,
  zero/one/two events, duplicate probes, masked task/depth/PPUCTRL gates,
  counter carry, overflow indication and production return-tail chaining.
  Four executed mutations are rejected. Original task bodies are controlled
  recorders here, not the actual sound engine.
- Priority oracle2922:104 cases exercise both preparation entry points,
  owned/unowned work, normal/camera interrupt frames, scanline cutoff and
  low stack positions. Two inverted-queue-branch mutants are rejected.
- Exact replay2918: all six recovery gates pass from checkpoint2233. The old
  completion counter stays134 on2239, then reaches135 on2240; the candidate
  reaches135 on2239. Pictures match through2240. Later timing/PCM differences
  remain visible; this is not whole-replay neutrality against the parent.
- New-core off/on replays2925/2926: all90 frames, full WRAM, CPU registers,
  actual two-port inputs and native PCM match their respective controls.
  Real queue accounting ends at three collected/three served, no overflow.
- Event audit2940: the bounded instruction window reconstructs from actual
  scanline clocks and proves three flag acknowledgments, three FIFO services,
  and one original body dispatch per queued service. Prior sound publication
  returns before each service; nine audio sender entries occur exactly once
  in native-event order. No unserved flag expiry appears in that window.
  This does not prove all nonqueued native events execute an original body.
- Fresh running2P combat2923:1751 two-frame intervals and **one three-frame
  interval2240→2243**. Busy original-NMI frames are included. Strict test FAIL.
- Route2924/renderer2927:9249 frames complete with neutral observation;
  audit2928 finds no split/stale/coverage failures. Actual park camera holds
  are east205×2+7×14 and west154×2+7×14: no short irregular holds. The longer
  encounter stops are retained, not filtered out of the histogram.
- Menu audits2935–2938: status opening/reopening, pause cursor return, two
  purchases and YES/NO movement match original-NES oracles. Broken controls
  remain rejected. Captures total19994 frames.
- Full-route DSP2939:8802 packets,1607 restarts, no late changed configuration,
  4,930,800 stereo frames at32040 Hz, peak6449, no clipping. Observer neutrality,
  actual packet transport and raw DAC/WAV identity pass. Deliberately late
  configuration is rejected. This does **not** establish perceptual fidelity
  or pop-free sound.

The nine-frame saved-state audio sender intervals are436014,269384,454556,
263502,493672,226012,457242,292374 master clocks. Their uneven timing remains
an open audio concern; intact packets alone do not mean steady music.

Full unit suite at this milestone:1223 passing (`/tmp/rcr-tests-2941.log`).
All original trial sources and reports remain unchanged and hash-bound.

## Cheaper read-path follow-up

Candidate2944 (`4635d1b1525f11345e76e8be8ed148af035408d06d0c3ba94f3be5cd37feefbc`)
adds an inline active-display test to each ring-read wrapper and calls a
shared collector only during VBlank. The wrapper restores P before the actual
load; the general collector still preserves A/P for the return-tail caller.
There is still only one actual flag-acknowledgment site and no extra WRAM.

Queue2945 and priority2946 repeat all234 executed cases and six mutations.
Measured cost2953 saves120 master clocks in each of24 active-display wrapper
calls (two load modes, flags, banks and stack positions). This excludes the
unchanged caller JSL/JSR and is not a whole-game speed ratio. Trace-on/off
full fixture WRAM matches the original oracle in every timing case.

Replay2947 retains all six exact-state recovery gates. Neutral clock
replays2950/2951 and event audit2952 again prove three collected/services,
nine ordered audio packets, no queue overflow and no unserved flag expiry.
Packet intervals are433668,271714,444152,273908,480616,239082,456810,292394.

Fresh combat2948 still fails:1751×2 and one3-frame interval2248→2251, with
three native NMI advances during that interval. Thus cheaper collection has
not solved the broader pacing issue. This candidate has no new full-route,
menu, DSP or physical qualification. Neither queued candidate is promoted;
offline baseline2769 is retained.

Fresh instruction control2954/window2955 reproduce all4928 frames and PCM
without observation changes; their full timeline/PCM also match the separate
combat-observer core's run. The remaining interval starts2248 at line171,
finishes2251 at line69, and starts its next main iteration at line96. Actual
hardware NMI entries occur at line240 of2248,2249 and2250; no queued service
occurs inside this interval. Thus this particular delay is **not another lost
hardware VBlank entry**. Original main work plus interrupt/preparation work
finishes late. Whether retained original-body work is accounted for correctly
under newer event identities, and where its time budget can be reduced, remain
open; hardware-entry counts alone do not prove that original-body invariant.

[Cheaper polling, exact remaining interval and replay audio](http://127.0.0.1:8766/queued-read-poll-review-2957/)
binds the measured120-clock savings, saved-state recovery and this failure to
the exact same2944 cartridge. Three new diagnostic tests reject a missing
hardware entry, a changed sparse/full-trace clock and an extra queued service
when classifying the interval. No performance threshold was relaxed.

Follow-up audit2959 identifies the concrete single-slot fallback: actual ROM
`$00817C` executes at2249 line255:1140. Its unchanged bytes clear `$1CE0`,
increment the served/fallback counters and dispatch one original body. The
source's `@deferred_fallback` explicitly leaves the new event unscheduled.
The interval has three hardware entries but only two original-body entries.
This establishes a specific scheduler repair target, not that arbitrarily
adding ticks is safe or that no other performance bottleneck remains. Retain
both real events while preserving original-body ownership and exactly-once
audio publication; cover that second-VBlank case with an executed fixture.

Final suite:1228 tests pass (`/tmp/rcr-tests-2958.log`); `git diff --check`
passes. Review2957 verifies2172 source bindings, seven artifacts and two exact
WAV files, and was visually inspected. Audit2959 separately binds the later
fallback diagnosis to the recorded trace and actual cartridge bytes.

The first2947 replay invocation and2948 combat invocation rejected incompatible
cores before capture; exact required cores were then selected. Cost2949 is an
incomplete failed setup, superseded by2953; no evidence was overwritten.
