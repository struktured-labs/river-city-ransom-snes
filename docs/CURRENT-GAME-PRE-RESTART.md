# Current-game pulse setup before hardware restart

[Native excerpts, game context, and all selected intervals](http://127.0.0.1:8766/game-prerestart-review-3150/).
Cartridge3065 remains unchanged. No MiSTer or OBS access occurred; Rivalmage
remains off-limits. This work extends the earlier replay-only pitch observations
to actual current-game scheduling. It is not a new hardware build or pop fix.

## Observation and controls

Plan3146 selects36 of1,607 current-game pulse restarts using **register timing**,
not waveform peaks: up to eight longest changed-volume, changed-pitch, and
changed-source setups per voice, plus four shortest changed setups per voice.
Duplicates are retained once with all selection reasons. Overlapping ranges
merge into29 observer windows containing4,600 DAC samples. This population
includes menus, title, and gameplay; it is not a representative random sample
or a whole-route absence test.

The existing read-only all-voice core2292 runs normal3147 and observed3148.
Both complete9,248 frames. Their full timelines, RAM, images, input, callback
sample counts, and native PCM are identical. The normal also exactly matches
the prior current-game route3068. The observed DSP-write trace and raw DAC
are byte-identical to the prior3069 observations used to choose the windows.
Thus changing observer core did not silently move the selected event clocks.

Every selected sample is reconstructed through all eight voices, stereo voice
mixing, master/echo mixing, and final mute. Actual DSP writes independently
explain control values. Native DAC equals delivered32,040Hz stereo S16 PCM.
Received packet bytes and expected restart schedule pass the existing gate.
The pitch oracle uses separate actual low/high DSP read phases, not just the
register values at the time of the sample. An altered real voice-contribution
record is rejected by the same reconstruction checker.

## Result

All36 selected setups contain some nonzero old-voice output before hardware
restart. **That alone is not a defect**: it also includes ordinary continuation
of the preceding note. Three selected samples have split-byte pitch values;
two have zero voice contribution and one has nonzero contribution:

| Packet | Voice | DAC sample | Actual pitch | Complete old/new | Stereo voice contribution |
| --- | --- | --- | --- | --- | --- |
|129|pulse2|264,564|960|789 /704|0 /0|
|688|pulse1|566,277|605|553 /1,117|0 /0|
|6,222|pulse2|3,538,382|799|935 /1,055|−215 /−215|

At packet6,222, source execution is at SPC tick113,228,226; the software KON
write is113,228,315 and its hardware latch is113,228,354. Envelope496 and
nonzero pulse output precede that latch. This confirms a current-game instance
of the **known remaining non-atomic pitch update**, despite correct final
configuration before restart. It does not establish the magnitude of the
counterfactual waveform difference or a causal link to physical pops.

The current engine already incorporates the five-clock publisher from
[the earlier word-pitch work](WORD-PITCH-UPDATE.md). Reapplying that optimization
would not fix this residual event. Any further change must preserve real note
resets and be evaluated against the original NES and existing timing gates;
muting every transition or filtering the evidence is not a justified fix.

## Harness details and retained failure

Use `tools.check_game_prerestart` for planning and captures, then
`tools.review_game_prerestart` for the review. Initial audit3149 stopped at an
overly broad uniqueness assertion: both voices legitimately restart more than
once during bootstrap packet0. Its log is retained and it produced no report.
The review keys each latch by **packet, voice, and actual KON-write tick**;
duplicate identities still fail. No capture or prior binding was rewritten.
The initial `audit` subcommand remains historical, not the authoritative review.

Six new tests cover timing-only deterministic selection, unchanged-state
exclusion, window merging, missing/wrong latch data, distinct bootstrap
restarts, and detection/rejection of synthetic split-pitch samples.
**1,289 tests pass**, `/tmp/rcr-tests-3151.log`; `git diff --check` passes.
All55 review source bindings and nine artifacts were rechecked. Four native
excerpts are exact source-WAV slices, without gain, normalization, resampling,
or phase fitting. Their screenshots match retained game frames. The rendered
page was inspected. No subjective listening or physical-audio pass is claimed.

The completed observation supplies an exact current-game event for a bounded
causal experiment. It does not justify another blanket transport or smoothing
change. Full-game speed, scrolling coverage, and physical audio acceptance
remain open; Bluemage capture routing is still unconfirmed.
