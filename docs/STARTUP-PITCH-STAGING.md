# Offline restart-only pitch staging

[Executed timing, native audio, and deliberately broken controls](http://127.0.0.1:8766/startup-pitch-review-3179/).
[Existing NES-reference gates](http://127.0.0.1:8766/startup-pitch-reference-3181/report.json).

This is an implemented SPC prototype, **not a promoted game cartridge**. The
current3065 game, graphics, controls, both MiSTers, and OBS remain unchanged.
Rivalmage remains off-limits. The previous turn observed a nonzero split-pitch
sample during a current-game restart; this experiment prevents that mechanism
in the tested restart windows without suppressing the note reset.

## Implementation

`build_startup_pitch_trial.py` starts from the exact current engine
`c880c1c1c5174305a8a8256809c55d4b6dc44cd21237b019eace5dc902c28a76`.
When a voice has a pending reset/duty restart, its publisher stores the computed
low/high pitch in new private SPC RAM instead of exposing the pair to the old
voice. SRCN and volume continue through the existing path. The flush issues
the original KON mask, waits a bounded instruction loop, and writes only the
staged voices during hardware startup silence, before their first advancing
oscillator sample. It clears staging validity and the pending mask before ready.

The helper is at SPC$3500; validity and two pitch pairs use$35F0–$35F4.
Upload grows from12,415 to12,800 bytes. Both experimental arms upload the same
length: baseline has only appended zeros. Engine bytes, upload size, and input
stream are separately bound. Ordinary updates retain the existing five-clock
low/high DSP gap and values, **but their instruction cost is not unchanged**.
Ordinary-update split samples are not fixed by this experiment.

## Executed checks

State report3159 executes201,060 publisher-plus-flush cases: every11-bit
period, both voices, enable/sweep/volume/envelope cases, two-voice boundaries,
and all four pending masks. All final DSP registers and application DP state
match baseline. Only DSP address/data MMIO shadows$F2/$F3 are exempt: changing
which register is written last necessarily changes those two shadows. They
differ in42,479 cases; no actual DSP register is exempt. A test changes each
of384 snapshot positions to check that the exemption is limited to those two.
An executed wrong-staged-high mutation fails2,603 of2,617 selected cases.

Measured additional publish-plus-flush cost:

| Pending mask | Additional SPC clocks observed |
| --- | --- |
|0, no restart|11,44,77|
|1 or2|128,161,189,222|
|3, both voices|128,189,250|

All16 continuous clock/receiver cases pass: baseline/trial, two frame-counter
modes, four sender delays. Actual timer deadlines remain within the existing
bounds; no prohibited volume writes occur. These are not full-game speed tests.

Two fixture families have fresh same-core normal/observed captures, exact
observer-neutral native audio/RAM/timeline/images, verified actual packet
receipt, and exact DAC/WAV equality:

- Held reference3152:32 restarts across four duties and two pitches.
- Changing cases3160:168 restarts, including either/both voices, large pitch
  changes, byte boundaries, enabled zero-volume restarts, and volume restoration.

All200 trial restarts write pitch inside the checked startup interval and
start at the correct pitch. Actual source output is zero for all1,000 retained
startup samples at indices1–5; envelope is zero at indices1–4. Configuration
timing is checked against actual KON consumption and the separate per-voice
DSP pitch-read phases, not packet ready or a fitted CPU/SPC clock relationship.

Changing cases cover53 of64 KON-write phases; held cases cover25. Across the
changing cases, the earliest low write has23 clocks of margin after measured
startup silence begins; the latest high write has36 clocks of margin before
its first advancing pitch read. This is measured coverage, not a claim that
all phases or physical implementations were exhaustively qualified.

Executed controls alter only the wait count. The early variant fails138 of168
startup-window checks. The late variant fails all168, with54 wrong first
pitches/stale nonzero onsets. Their final source inputs and intended notes
remain unchanged; the failures demonstrate sensitivity to real execution order.

## Retained failures and limits

Cross-arm callback timing is **not exactly equal**:

| Fixture | Different callback boundaries | Baseline / trial native samples |
| --- | --- | --- |
|Held|115|769,753 /769,753|
|Changing|174|1,145,070 /1,145,071|

Source-frame/input sequences and player host-frame cadence match. The observed
boundary differences are one sample; all are retained. No trimming, retiming,
resampling, normalization, or dropped-frame masking is used. Each observer's
same-core control still matches exactly; that is distinct from cross-ROM equality.

Reference3181 reapplies the original eight NES transient gates without changing
limits. Baseline and trial each pass seven. Period$06C6/duty0 still fails the
relative-step bound with ratio1.0. All fundamentals pass and the five-sample
startup quiet duration remains0.156055ms. These held-tone checks do not establish
better changing-note sound or fix the remaining waveform/DC/noise differences.

The prototype is not integrated into the game. Added service cost, changed
callback boundaries, larger upload, actual gameplay restart coverage, graphics/
DMA deadlines, original-NES changing-note fidelity, and physical audio all
need qualification. The precise current-game packet6,222 event has not yet
been replayed under the changed full-game engine. No physical-pop or subjective
listening verdict is claimed.

## Evidence and reproduction

Authoritative outputs: fixtures3152 and3160, state3159, onset3157/3165,
early/late fixtures3172/3173 and captures3174–3177, review3179, reference3181.
Review3179 binds132 sources and five artifacts; its four native excerpts are
exact WAV slices. The page was rendered and inspected.

Preliminary state3158 rejected MMIO shadow differences. The checker was then
corrected before publication, so its old source hash is superseded;3158 is not
accepted qualification evidence.3159 is the fresh execution. Earlier negative
fixtures/captures were also regenerated after review-source changes; only
3172–3177 are used in the published source-bound review.

Six additional unit tests cover helper/storage separation, preimage/delay
guards, the two-byte MMIO exemption, both-voice/muted stimuli, actual startup
timing limits, and retained cross-arm sample differences. **1,295 tests pass**,
`/tmp/rcr-tests-3180.log`; `git diff --check` passes. The full speed, scrolling,
and audio goal remains open.
