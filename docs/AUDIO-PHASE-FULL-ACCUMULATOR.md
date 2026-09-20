# Real IRQ-return corruption and complete-accumulator repair

**3665 is rejected for deployment.** Its pause-timing improvement and broad
graphics/audio checks were real, but a stronger CPU-state check exposed an
interrupt-handler bug. This supersedes any interpretation of those earlier
passes as sufficient qualification.

[Broken/fixed register evidence and native audio](http://127.0.0.1:8766/audio-phase-full-a-review-3686/).
This page was rendered/inspected and its linked WAV returnedHTTP200.

## What the broader3665 checks actually established

Fresh neutral full-route observations3673–3677 each completed9090 frames.
DMA control matches the primary core's entire video/input/state timeline and
native PCM; DMA observation matches that same DMA core's control. Renderer
observation likewise matches its own exact-core control. Audio/main observation
matches primary3672. Audits3678/3679 and review3680 establish:

-7473 eligible actual rendered frames, zero missing coverage, split scrolls or
extra-frame stale-camera failures.
-53163 general DMA envelopes:1918 forced-blank,51241 VBlank,4 other; no unsafe
envelopes, latest visible completion258. Active-scanout, crossed-frame and
unfinished-transfer controls are rejected. HDMA is outside this audit.
-8641 sound packets and1588 startup checks pass. Native PCM has no clipping;
this is not a pop-free verdict.
-3668 eligible room-loop intervals all take two frames:598/1746/477/847 across
rooms0–3. Busy-marked intervals are zero in these populations. Excluded and
censored records remain in JSON; this does not establish equal-work NES speed.

Review generation took54.466s, separately from captures. These are scoped
historical results for3665, NOT inherited passes for the repaired cartridge.

## Stronger test: inspect actual IRQ returns

`tools/audit_audio_irq_returns.py` pairs actual scheduler entry, original RTI,
and the first resumed instruction in the neutral1430–1445 trace. All16 returns
on3665 damage A.high (the hidden B byte in emulation mode). First example:
`$2601 → $1E01`. X/Y and stack matched; the low accumulator byte alone would
have hidden the failure.

The sound publication bridge uses native-width accumulator operations. An
8-bit PHA/PLA around it cannot preserve the high accumulator byte. The isolated
asset-free spy never modified that byte, so its PASS did not cover this defect.
The real failed report3681 is retained as the negative control. Four independent
unit tests also reject changed hidden B/X/Y/stack, censored and reentrant returns,
and a non-RTI opcode. Their synthetic page-wrap checks validate the checker,
not actual game safety at every possible stack depth.

## Repair and current candidate

3682: `build/audio-phase-full-a-game-3682/native-cpu.sfc`
SHA256 `4578e026751366607e4827bbf79c4c2f7dff9dd96455f510d6f3f82f5c5db034`.

`snes/audio_phase_full_a.asm` explicitly saves/restores both accumulator bytes
around actual IRQ service. Arming, NMI fallback and critical-section recovery
also preserve hidden B around the old implementation; recovery still returns
the interrupt-enable policy in A.low and corresponding N/Z flags. The driver,
SPC engine, graphics assets and tick ownership are unchanged. Exact3682 derives
from source-bound3665 through `tools/build_audio_phase_full_a.py`.

Fresh pause3683 completes2537 frames. Observer3684 reproduces every primary
timeline row and native PCM exactly. Review3686 confirms all16 actual IRQ
returns preserve full A/B, X/Y and stack; first example `$2601 → $2601`.
Native onset3685 remains57 frames, matching NES57, and rejects delayed/dead
controls. The corrected handler did not lose the measured audio improvement.

## Still required

P/DB/DP are not in the existing instruction observer, nor does this bounded
check reconstruct the independently intended return PC. Those properties,
expanded IRQ phases and critical-section recoveries need direct evidence.
The two late fallbacks in the pause route also need investigation. Broader
graphics/cadence/acoustic qualification must be repeated on3682; a fresh
park traversal3687 now completes9091 frames with zero adapter faults and no
requested/delivered input mismatch. Terminal counters are7455 scheduled and
7455 served, pending0/fallback0. These basic checks do not replace the new
cartridge's pending renderer/DMA/cadence/PCM audits. Neither3665 nor3682 was deployed.
Original-game speed, full scrolling behavior and physical pop-free audio remain
open requirements, not conclusions from these internal gates.
