# Fused sprite copy: exact-encounter deadline improvement

[Before/after screenshots, raw audio and full differences](http://127.0.0.1:8766/sprite-deadline-review-3309/)

Experimental guarded candidate `sprite-fused-guarded-game-3303`, ROM SHA-256
`9309c238d84da3803673c1415d629e0383e04d5e388a72d415d44aac0c7abbb3`,
combines the original sprite-page copy with incremental conversion. One source
load serves both purposes. It preserves the earlier converter for initialization,
transitions, non-game tasks, other source pages and pattern-half changes. No SPC
engine bytes or original sprite artwork changed.

Instruction observation 3298 found the previous post-copy helper spending about
13,000 master clocks scanning an unchanged page, in addition to the original copy.
This consumes roughly 9.5 scanlines and contributed to a three-frame game update
in the two-player encounter at frames 2239–2242.

## Exact-state result

Checkpoint 3306 at frame 2200 comes from the failing sprite-copy3252 encounter.
The full 4,929-frame checkpoint capture matches its same-core uninterrupted
control, including PCM. Same-ROM resume3307 reproduces all 80 resumed frames'
video, game RAM, registers, input and PCM exactly.

Trial3308 restores identical full WRAM and saved CPU registers, then runs exactly
the same recorded two-port input. The new wrapper requires emulation mode at the
checkpoint, outside the native converter, and freshly rebuilds the permitted
patch before allowing the trial. No trace-clock adjustment or input retiming.

- Before: 37 fully witnessed two-frame completion intervals and one three-frame
  interval. After: all 38 fully witnessed intervals are two frames.
- The original $052B update at frame2242 now arrives at2241; neither branch skips
  or resets the counter. Initial/final incomplete intervals are not invented.
- 55/80 whole-frame pictures and 33/80 PCM chunks remain byte-identical. All game
  RAM/register frame-end snapshots differ as execution timing changes; retained
  raw differences are not waived into an equality pass.
- Inputs and adapter-fault checks pass all80 frames. This is a same-start-state
  SNES comparison, not original-NES speed or pop-free audio qualification.

## Other results and remaining work

Focused sprite cycle3304 passes: all20 known generations appear next frame;
original source-generation timing, game counters, camera and inputs match across
the2,099-frame prefix. Fresh observer/control cycle took11.34seconds.

The initial unguarded fusion3300 changed story timing by one frame and failed the
focused equality gate. Its evidence3301 is retained, not used as qualification.
The gameplay-guarded3303 passes that prefix but releases a later street transition
three frames earlier in an independent combat run3305. Stable combat intervals
are two frames, but the strict campaign still fails around a later room transition.
Different fresh encounters do not establish equivalent speed; this is why the
exact-state replay was necessary.

Not promoted, pushed, deployed or tested on either MiSTer. Still needed: execute
the fused helper's complete byte-conversion and return-register contract matrix,
resolve/qualify the strict combat transition, then run exact-build renderer, DMA,
menus and native-audio checks. Parent3252's broader checks do not qualify3303.

The `romhack-test-loop` skill led to retaining the failed fresh comparisons and
using a proven exact-state short replay before another broad campaign. Four new
cadence tests reject a frozen counter, skipped counter, missing frames and a
three-frame stall;14 focused tests pass including patch/shop/issue-tracking tests.

## Follow-up: broad qualification and the second stall

The historical remaining-work paragraph above describes the initial3303 result.
Subsequent3312 runtime tests executed31 byte-conversion/ABI cases and rejected
wrong-Y and lost-X mutants. Fresh3303 renderer, DMA, menus and audio checks passed
their scoped gates; see [qualification3340](http://127.0.0.1:8766/sprite-fused-review-3340/).
Neither that report nor its stable-combat classification establishes full speed.

Sustained-combat3337 then found another three-frame update,4825→4828. Exact
instruction trace3341 shows retained original-NMI work crossing the frame boundary
with native NMI masked; re-enable occurs at4827 line7. Main-loop admission waits
until line96. The new isolated3342 experiment advances that threshold to80 in all
eight mirrored helpers; only eight operands and cartridge checksum change.

[Phase80 exact-state collage and native audio](http://127.0.0.1:8766/fused-phase80-deadline-review-3351/)

- ROM SHA `3efb309fbcf3b2b7a8814e3899a5620d6bd13472e9c849506200499da1f292c3`.
- Checkpoint3343 reproduces the complete4926-frame control. Same-ROM resume3345
  matches all70 frames' pixels, RAM, registers, inputs and native PCM. Trial3346
  starts from identical complete WRAM/registers and two-port input, after a fresh
  rebuild proves the permitted patch. Original initial WRAM witnesses the first
  counter change rather than censoring the failing interval away.
- Before:33 two-frame intervals plus one three-frame interval. After:34 two-frame
  intervals. The delayed update completes4827 rather than4828. All later state,
  image and PCM differences remain recorded, not treated as equality.
- Fresh sprite cycle3344 passes all20 next-frame publications and unchanged
  prefix source timing/counter/camera/input in12.09seconds.
- Renderer3348/3349 completes9248frames with exact same-core observer neutrality;
  audit3350 finds no coverage, split or stale-camera failures in7640eligible frames.
- Display cadence3353/3354 matches3303 in both park sweeps: zero short irregular
  uniform-endpoint holds. Long holds remain in the reports, including stops up to
 168frames; they are not discarded or certified as original-speed equivalence.
- Both fresh two-player3347 runs complete4927frames. Sustained combat passes its
  strict gate; busy-inclusive intervals are1752×2. Running/jumping has1710×2
  busy-inclusive stable intervals, but strict15- and24-frame room-load spans
  remain failures. Different encounters are not matched NES-workload comparisons.

No deployment. Phase80 still needs fresh DMA/menu checks and room-load
qualification; native restart correctness is not a claim that audible pops are
fixed. The test-loop skill required the exact-state symptom improvement and actual
display cadence check before wider acceptance. Parent results are not inherited.

Audio3355–3357 completes9248frames with exact same-core observer neutrality.
All1611 staged restarts have correct first pitch and no stale nonzero startup;
four-room cadence passes.8802 received packets are retained. Commands and PCM
differ from the older3065baseline, so no audio-equivalence claim is made.
[Current scoped checks3359](http://127.0.0.1:8766/fused-phase80-checks-3359/)
preserves the strict combat failures and acoustic limits.1342 unit tests pass
in12.08seconds (`/tmp/rcr-tests-3358.log`); no hardware changes this iteration.

## Exact-build follow-up: DMA, menus and NES load visibility

Candidate3342 remains unchanged. Fresh general-DMA controls3361/3362 preserve
all9248frames and native PCM. Audit3363 passes all56323whole transfer envelopes:
54484VBlank,1835forced-blank and4other transfers; latest visible-frame end257.
Active-scanout, crossed-frame and unfinished-transfer mutations are rejected.
This observes general DMA, not HDMA or physical per-byte timing.

Fresh menu captures3364/3365/3373/3374 pass the existing original-NES oracles:
Present Status initial/reopened numbers, pause cursor return, two purchases and
YES/NO cursor navigation. Initial3366/3367 were mistakenly run with waypoint
shop policies; the unchanged checkers rejected their different scenario hashes.
They are retained, not accepted or relabeled. Correct fixed-input reruns pass.

Freshly recomputed room-entry3372 compares the first observed entry in each room
against the authenticated original-NES331 capture. All40 fixed-offset background
bands per room match. Every first scenery pixel arrives7frames after rendering
enable, on both systems. Total room-change-to-visible frames are:

| Room | NES | Phase80 |
| --- | ---: | ---: |
| Alley1 |20|20|
| Mall2 |31|27|
| Park3 |30|27|

New ordinary-input school-return3377 completes2877frames. Audit3378 matches all40
return-fade background bands against NES2140: room-change-to-visible34NES versus
29SNES; rendering-enable-to-visible7frames each. Independent encounters and
different amounts of work remain; these are visibility/fade comparisons, not
matched-work speed ratios. The running-jump strict15/24-frame spans remain in
the raw combat report; a universal two-frame criterion also fails on original
NES room loads. These longer spans alone do not establish a port regression.

No ROM patch or hardware operation was needed for this qualification. Physical
speed/audio acceptance and the cause of reported popping remain open. Current
game audio should be auditioned from its native waveform, not from the old3359
page's empty fixed-packet excerpt section: that excerpt was omitted because
commands differed from the older baseline.

[Follow-up3379: menus, loads and native audio gallery](http://127.0.0.1:8766/fused-phase80-completion-3379/)
includes the entire unchanged153.8785second recording and eight largest separated
sample-step clips, each with its exact game frame. All4930267stereo samples at
32040Hz are covered by9248consecutive callbacks. No clipping; maximum step3340.
All>=10ms exact-zero runs remain recorded. Synthetic full-scale edge, clipping
and50ms silence controls are detected. These metrics do not identify unwanted
pops or distinguish intended rests from dropouts. Clips decode exactly to their
source slices with no resampling/normalization. Early report attempts correctly
rejected the old physical-audio helper's48kHz constraint and a float-valued sample
rate; the new native-rate helper has four dedicated tests.1346tests pass in11.84s
(`/tmp/rcr-tests-3380.log`), and the rendered gallery was inspected.
