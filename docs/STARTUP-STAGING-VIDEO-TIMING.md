# Restart staging: video timing and lower-overhead tail variant

[3190 menu/DMA collages](http://127.0.0.1:8766/startup-pitch-extended-3218/).
[3190 changed-frame diagnosis](http://127.0.0.1:8766/startup-pitch-video-differences-3215/).
[New3219 audio timing and native clips](http://127.0.0.1:8766/tail-startup-pitch-review-3223/).
[New3219 changed frames](http://127.0.0.1:8766/tail-startup-pitch-differences-3225/).

This iteration qualifies the preceding3190 cartridge further, identifies
video-stage timing differences, and implements a lower-cost SPC variant3219.
Neither is promoted or deployed. Rivalmage, Bluemage and OBS remain untouched.
The preceding turn was progress; this turn adds executed evidence and code,
not a wait for hardware availability.

## Completed qualification of3190, not automatically transferred to3219

The exact3190 ROM remains
`e1d5936b580f9faa6b766658e99b2e8537be843366dc292e0dd2c3850b47a2ea`.

Fresh menu captures3204–3207 cover19,990 frames. Original fixed-region pixel,
CIRAM, shadow, VRAM and numeric-state checks pass for Present Status opening/
reopening, pause cursor return, repeated café purchases, and YES/NO traversal.
Retained known-broken cursor/shop controls still fail. Audits3208–3211 are
independently re-evaluated by combined review3218, not just accepted from a
stored green flag.

DMA normal3201 reproduces the preceding3191 route exactly. Observed3202
reproduces3201 with the same core:9,248 frames, complete timeline and native
PCM. Audit3203 classifies all56,233 general transfers:

| Class | Transfers |
| --- | ---: |
| Display-memory envelope within VBlank |54,390|
| Display-memory envelope with forced blank at both endpoints |1,839|
| Other target/direction |4|
| Aborted or unsafe/unproven |0|

The latest visible transfer ends on line257. Active-scanout, frame-crossing
and unfinished-transfer mutations remain rejected. This covers general DMA
envelopes in this route, not HDMA or physical per-byte transfers.

## What the changed pictures actually show

New `capture_video_pipeline_state.py` reads end-of-frame WRAM sprite-source,
prepared-OAM, cached-source and palette stages without writing emulated memory.
It also records the existing diagnostic background plane at actual renderer
flushes. Both captures must reproduce their own **same-core** control exactly,
including all primary pictures, game RAM, inputs, timeline and audio. Original
game-RAM hashes independently align every snapshot to the primary frame.

The first attempted parent capture3212 correctly rejected a different-core
control before emulation/output creation. Parent3214 uses the existing neutral
same-core3147 control; trial3213 uses3191. Both complete9,248 frames and pass
neutrality. No control check was relaxed.

Audit3215 retains all365 changed primary frames and every differing original
RAM byte. Of60,409 changed pixels,40,157 lie over equal supported background,
17,531 over changed supported background, and2,721 have unsupported background
coverage. Unsupported pixels are **not** treated as equal. Matching backgrounds
narrow a difference to non-background composition, not necessarily OAM alone.
The gallery ranks the largest difference in each phase; the complete population
remains in JSON, without frame alignment or masked primary comparisons.

There are77 different prepared-sprite snapshots. In76, both builds have equal
NES OAM source data:

- 40: parent cache matches the current source, trial cache does not.
- 33: trial cache matches the current source, parent cache does not.
- 3: neither cache matches the current source.
- The remaining 1 has different source data, and both caches match their source.

For example, frames1989–1990 have equal source data while3190 still has an
older prepared generation. Conversely, other frames favor3190. These snapshots
establish preparation differences even when sprite source data agrees. They
do not prove absence of other game-state divergence, establish exact OAM DMA/
display latency, or excuse either build's changed pictures. Actual publication-
event tracing remains a useful next diagnostic.

The largest3190 difference is frame5972:7,604 pixels during alley entry. That
frame also has different source and prepared palette snapshots. This is not
silently grouped with sprite-only differences or declared an improvement.

## Implemented lower-cost3219 variant

- ROM: `d606bd1d898f7654e726010e8d78bb0b17adf786b73e05141f1601b73d9a1a45`
- SPC: `f22ccdd429c64fc8eb0f7e830ab8183fb938f0cbc85fe75babf11b0d371e009a`
- Cartridge: `build/tail-startup-pitch-game-3219/native-cpu.sfc`

`build_tail_startup_pitch.py` replaces the staging dispatch's extra CALL/RET
and executed NOP padding with guarded tail jumps. A direct-page bit-clear
branch tests pending restart without clobbering the already-loaded high DSP
register selector. Both paths jump back after the original seven-byte pitch
tail. Helpers fit inside their existing extents; upload remains12,415 bytes.
No game CPU, graphics, controls, loader or receiver code changes. Ordinary
low/high pitch writes retain the existing five-clock gap; restart flush and
silent-startup staging remain intact.

The existing actual SPC state, lifetime-mutant and continuous-timer oracle is
reused with only its expected patch function substituted. Wrapper source and
the explicit substitution are bound in state3220. All201,060 cases pass, with
only the previously specified DSP MMIO shadows$F2/$F3 exempt. All actual DSP
registers are compared. The stale-validity mutant fails25/4,452 cases; all16
continuous timer/receiver cases pass.

| Pending mask |3190 additional SPC clocks|3219 additional SPC clocks|
| --- | --- | --- |
|0|0,32,64|0,13,26|
|1 or2|124,156,182,214|124,137,165,178|
|3|124,182,240|124,165,206|

Thus ordinary active-pulse overhead falls32→13 clocks per voice. This is a
measured helper-cost reduction, **not** a percentage increase in game speed.

Full-game normal3221 and observed3222 are same-core exact over9,248 frames.
Audit3223 verifies all8,802 complete CPU packet records unchanged from3065,
all1,607 restarts staged in measured startup silence, zero wrong first pitch
and zero stale nonzero onset. Four-room main-loop cadence passes. The gallery
and untouched native full-mix excerpts remain available for audit; no claim to
have heard an acoustic improvement is made.

Fresh neutral video-stage capture3224 and audit3225 retain321 changed images
versus3065, down from365 for3190. Changed-pixel totals fall60,409→35,771:
24,922 over equal supported background,9,825 over changed background,1,024
unsupported. Prepared-sprite differences fall77→55. Using the same source/cache
comparison, equal-source parent-current/trial-stale cases fall40→18; reverse
cases are32, neither-current cases4, different-source cases1. Palette snapshots
no longer differ. These are diagnostics against3065, not original-NES correctness
gates or proof of visually smooth publication.

Not every measure improves: nonaudio timeline-difference frames increase
8,462→8,514 and callback-boundary differences830→884. All are retained. This
prevents describing3219 as a fully timing-equivalent or unconditionally better
cartridge merely because it executes fewer instructions.

## Verification and next work

All1,306 unit tests pass (`/tmp/rcr-tests-3226.log`); `git diff --check` passes.
New tests cover read-only snapshot extents, missing background coverage,
independent primary/background difference populations, cache correspondence in
both directions, guarded tail preimages, branch targets and resume addresses.
Reports bind their inputs, ROMs, cores, observers and generated artifacts.

3219 still needs its **own** menu, DMA, renderer and two-player combat runs;
3190 passes cannot be transferred across the engine change. Sprite/text
publication timing, original-NES waveform/full-game speed coverage and physical
Bluemage audio/video remain open. This does not close the user's popping or
slowdown reports. Splash sound and controller modes were not changed this turn.
