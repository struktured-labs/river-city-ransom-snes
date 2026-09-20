# Retained job identity and active-scanout wait

**Hardware restriction:** Rivalmage is occupied; do not use it. The user permits
Bluemage instead. No MiSTer interaction, upload, restart or OBS change occurred
in this work. The candidates below remain offline.

Candidate2971 `build/retained-wait-trial-2971/native-cpu.sfc`, SHA
`ca5682e352d29f3a4231ba9784155a2b8c6b81f41b044716b96f67ba06fb2afd`,
fixes the observed single-slot fallback loss from the preceding
[queued-VBlank investigation](QUEUED-VBLANK.md), and a newly exposed active-frame
wait bug. It is **not release-ready**: fresh combat and an earlier picture gate
still fail. Offline baseline2769 is retained.

[Latest review, including the failed earlier picture gate](http://127.0.0.1:8766/retained-followup-review-2989/)
links the [event-identity replay, first failed attempt and exact native audio](http://127.0.0.1:8766/retained-service-review-2984/).

## Implementation

The previous hardware handler incremented the native event ID before checking
whether the preceding original-game interrupt was still retained. Its fallback
served that older job under the new identity and left the new job unscheduled.

The new E1 entry at `$C17400` replaces the seven-byte native acknowledgment
prefix. After reading the actual `$4210` flag, it only takes the new path for
an already-retained gameplay job, depth0, and an early-audio token matching
the **old** native event ID. It queues the real newly acknowledged event,
clears the old retained slot, increments its original served/fallback counters,
and dispatches the old body without advancing the event ID. The production
return tail then assigns the queued event's ID and services or retains it
through the normal native kernel. Thus the old sound token is consumed only
for its matching old body; no synthetic sound-suppression token is invented.

Other admission cases preserve the prior entry path. Missing/mismatched early
tokens are explicitly outside this new path, not falsely claimed repaired.
The queue uses the existing `$1B87..8C` state; helper code fits in the previously
empty `$7400..75FF` slot in eight mirrors. Labels and original graphics/SPC
payloads are not relocated or modified.

First attempt2961 (`a3743c69f1821f70bed2d59823bd2a05d27c720021b42189589a237b117af868`)
exposed a second defect: queued native service could reach
`@deferred_late_vblank` during active display. That loop assumed entry during
VBlank and waited until line250, consuming nearly an entire display frame.
The next flag expired while masked. Candidate2971 checks the nonacknowledging
`$4212` VBlank bit before waiting: if display is already active, it continues
immediately. If still in VBlank, the original beam-latch reads and cutoff remain.

## Executed tests

- Checkpoint2960 saves2248/2249 without changing any of4928 frame observations
  or native PCM samples. Same-ROM90-frame control2964 passes completely.
- Real hardware-entry oracle2965/2973:44 cases execute the actual vectored
  VBlank NMI, native dispatch kernel, queue and production return tail.
  Cases cover bank/stack/flags, event-ID carry and wrap, queue/counter carry,
  retained/ordinary paths and token/task/depth admission. A second controlled
  camera return drains the newly retained job. A/B/P/X/Y/D/DB/SP are checked.
  Three executed faults (lost pending event, early identity advance, old slot
  not cleared) are rejected. Original body and audio transport are spies;
  this is not an SPC waveform test.
- Beam oracle2977:36 actual scanline cases from0 through260. At active line40,
  the old wait returns at250 and is rejected; the corrected wait returns near
  entry. VBlank cases retain the original250 cutoff. Continuations are beam
  and ABI recorders, not the rest of the real game.
- Original token-mismatch fixture2963 used a **future** ID equal to the next
  event and correctly caused the existing suppression macro to suppress it.
  The preserved failed fixture is not hidden. The subsequent stale-token
  admission case uses OLD_ID−1, matching the intended older-token scenario.
- Final full unit suite:1234 tests pass (`/tmp/rcr-tests-2987.log`).
  `git diff --check` passes. New tests reject missing/duplicate body or sound
  identities and the whole-active-frame wait; no release threshold is relaxed.

## Same-state original-body and sound ordering

Exact guarded replays2966/2972 rebuild only the permitted patch from parent2944.
New-core off/on pairs2967/2968,2969/2970 and2975/2976 verify all90 frames,
full WRAM, all CPU registers, actual P1/P2 inputs and PCM against their controls.
No RAM/register fixup is applied after restoring a state at the first native
hardware-entry instruction.

Review2984 reconstructs seven trace frames from1834 real scanline events and
actual ROM opcodes. Parent body IDs are1861..1866 but packets are1860..1866:
body1860 was lost. First attempt restores body ownership but loses the next
hardware flag. Corrected2971 has **all seven bodies and seven sender packets,
1860..1866, once each and in order**, with no unserved flag expiry. The actual
preflight acknowledgment is checked before identity assignment; the older body
runs under its already-published older audio ID before queued service.

From checkpoint2248, the corrected completion counter advances140→141 on2250;
the parent reaches141 on2251. Native counts and pictures match through2252.
After90 frames the candidate has completed185 updates versus184, and both
have native ID1949. This is a bounded same-state result, not equal subsequent
enemy work or whole-game speed parity.

Audio sender intervals remain uneven:448128,262054,437004,264174,433818,281442
master clocks in the corrected window. Intact ordering is not steady timing,
full-route DSP transport, acoustic fidelity or a pop-free verdict. Review2984
binds1534 source files,16 artifacts and three exact unnormalized WAVs; all were
reverified, and the page was inspected in Chromium.

## Full-route and retained failures

Route2980 and neutral renderer2981 complete9248 frames. Audit2985 finds zero
coverage, split or stale-camera failures. Actual eastbound camera holds are
205×2+7×14, westbound154×2+7×14; no short irregular holds. Fourteen-frame
encounter stops remain visible in the histogram.

Fresh running2P campaign2974 still fails:1751 two-frame start intervals and
one three-frame interval2250→2253. Full instruction control2978/window2979
match all4930 frames and PCM, including the separate sparse-observer core's
run. Audit2988 matches exact instruction/sparse start and finish events:

- Start2250 line221:1290.
- Finish2252 line239:530, after two native NMI advances.
- Another real NMI at2252 line240 runs before the next main iteration.
- Next start2253 line98:408.

The two-tick completion counter and the three-frame **start** interval have
different endpoints. Do not mistake this particular count of2 for a missing
hardware entry: two entries precede completion and one follows it. Preparation
and interrupt work still consume enough time to miss the normal phase budget.
Owned producer work before queued service is a candidate for the next measured
optimization; do not simply drop preparation or relax the pacing gate.

Earlier checkpoint2233 is also rerun by rebuilding the complete fusion→queue→
retained-entry/wait composition (replay2986). The2239 interrupt and completion
counters still recover, **but the old fixed-picture gate fails at2238/2239**.
Pictures match again at2240 while frame-end camera state differs. This has not
been qualified as harmless earlier publication; keep the failure and investigate
it before promotion. The follow-up review shows both full rows of frames.

New menu, full-route DSP, main-to-display latency, physical speed/audio and
original-NES parity qualification remain open for2971. No hardware deployment
is authorized by passing these narrower tests alone.
