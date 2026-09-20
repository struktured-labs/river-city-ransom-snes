# Ordinary-path audio: measured scheduling improvement

New offline trial3065:
`964ef6c71257b89c1f9097ca6b4e2f9418b530057d5235e83f5e85c8ebd6711c`.
Parent3032 remains available unchanged. Neither MiSTer, OBS, controller nor
saved setting was accessed. Rivalmage remains occupied/off-limits; Bluemage
is permitted for subsequent qualification. This trial is not deployed.

- [CPU scheduling diagnosis](http://127.0.0.1:8766/final-batch-audio-stages-3064/)
- [Paired native audio clips and screenshots](http://127.0.0.1:8766/ordinary-early-audio-review-3073/)
- [Qualification receipt](http://127.0.0.1:8766/ordinary-early-audio-qualification-3077/report.json)

## Cause found in the measured cadence

Fresh sparse CPU/SPC trace3063 reproduces all9,248 parent frames, input, original
RAM and PCM exactly. The CPU's host-only elapsed clock accumulates actual
`H_Max` values; there is no fitted CPU/SPC clock epoch. All8,802 publications
are joined to actual ACK completions and physical SPC byte receipts.

Within the7,609 frozen gameplay intervals,3,732 switch from normal NMI exit
to early retained-camera sound service; another3,732 switch back. The driver
entry medians are323,462 and391,380 CPU master clocks, respectively: roughly
15.06ms and18.22ms.145 remaining intervals are normal-to-normal. The largest
completion gap has454,744 clocks between driver entries; the later driver
starts at scanline60 after the previous entry at251. This explains much of
the alternating *measured scheduling*, not by itself an audible-pop verdict.

One transition sound call spans native IDs5909→5910. It is retained explicitly
as split-event evidence, not silently forced into same-event correspondence.
It is outside the frozen stable-gameplay timing population. Other packets
without a driver call remain visible, rather than inventing driver endpoints.

## Implementation

`snes/ordinary_early_audio.asm` adds an experimental dispatch at the original
native `PLA / JML [$1C00]` site. The existing interrupted A and interrupt frame
are retained. Before dispatching the original game body, it invokes the
existing early-audio helper only for gameplay taskC0, original busy clear and
transition state0. Menu, busy and transition paths retain their old timing.

An already-valid token with the exact16-bit current native ID skips service;
the original NMI exit still consumes that token. A mismatched token is replaced
only by actually executing the sound update. This is important when an old
retained body is dispatched on a newer physical interrupt. No synthetic audio
event, skipped command or changed SPC engine is introduced.

The builder authenticates parent3032 and checks the full4-byte native dispatch
preimage plus unused512-byte ROM slots at$7600 in all eight game mirrors.
Only those slots, the dispatch and checksum change. No graphics assets change.
The original interrupt-body/audio ordering does change for eligible gameplay,
so independent menu, timing and picture qualification remains necessary.

## Actual audio result

Fresh normal3068 and observed3069 routes each contain9,248 frames. Per-arm
observer neutrality is exact. Between parent and trial, all8,802 ordered
23-byte packets and native event IDs match **byte-for-byte**. Controller input
and scenario phases are identical. Both traces validate1,607 pulse restarts
with zero late changed configuration writes and no clipped PCM samples.

The same7,609 gameplay event pairs are used in both timing populations:

| SPC completion interval | Parent3032 | Trial3065 |
| --- | ---: | ---: |
| Minimum ms |11.7548|14.4585|
| Median ms |16.5496|16.6618|
| p99 ms |19.4005|17.7617|
| Maximum ms |21.1454|18.7237|
| Standard deviation ms |1.6838|0.4822|

The standard deviation decreases **71.36%**. These are native nominal-rate
timings, not a71% game-speed improvement or proof of pop-free sound.
The DSP engine remains unchanged. Whole-capture peaks are6559 and6402;
amplitude reduction was not used to obtain the timing result.

The total PCM sample count and rate match, but884 callback rows have different
start/count boundaries: starts differ by at most one sample, counts by at most
two. All changes are retained. The six four-second WAVs use identical absolute
sample ranges and are byte-checked against native recordings; there is no
resampling, gain normalization or fitted local phase/time alignment.

321 rendered frame hashes differ from the parent. These are not hidden by
the unchanged command stream or input sequence. Selected screenshots are
context; exact sprite/picture and renderer gates are checked separately.

## Executed qualification

- 44 real hardware-NMI ownership/ABI cases pass with the actual new dispatch
  and existing queue/retained-return code. Original body and transport are
  explicit spies. An executed duplicate-old-audio mutant fails as expected.
- Combat3066: fresh same-core normal/observed two-player running-jump captures
  contain4,929 frames; strict and busy-inclusive checks pass all1,753 two-frame
  intervals, with zero irregular intervals.
- Full route renderer3070/audit3071:7,639 eligible frames covered; zero missing
  coverage, splits or stale-camera failures. Park east holds205×2 and7×14;
  west154×2 and7×14. No short1/3/4-frame irregular hold. Long holds remain
  explicit and are not a full-game original-NES speed certificate.
- Status3072/audit3074: opening/reopening fixed-region pixels and stat digits
  exactly match the original NES oracle.
- Pause audio3075: separated sound onset matches NES at offset57, with25
  preceding quiet frames. Two-frame-delay and dead-capture controls reject.
  This is onset timing, not waveform identity.
- Exact rebuilt cross-ROM replays3078/3079 preserve full initial WRAM/registers.
  Earlier2239 recovery passes all six existing gates, including pictures
  through2240. Newer retained completion advances at2250 instead of2251;
  pictures match through2252. That newer parent's native counter already
  advanced at2250, so it is not falsely labeled a missing-counter recovery.

Full suite:1,253 tests pass after the final changes (`/tmp/rcr-tests-3080.log`);
the six directly affected stage/patch tests also pass separately.
`git diff --check` passes. Review3073 includes a changed-payload negative
control; an initial attempted zero-fill mutation hit an already-zero packet,
was correctly detected as ineffective, and was replaced by a guaranteed
one-bit mutation before publication. No report success was inferred from it.

## Next work / limits

Finish the other three menu regressions and reassess late-DMA admission under
the changed overall interrupt schedule. The production final-batch bytes are
unchanged, but its prior fixtures do not prove every newly reached call phase.
Continue original-NES speed/fidelity comparisons and Bluemage physical audio
self-testing. No physical, full-game, pop-free or release-ready verdict yet.
