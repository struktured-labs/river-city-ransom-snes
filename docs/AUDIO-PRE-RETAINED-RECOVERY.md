# Post-preparation sound recovery: two measured, unpromoted variants

No hardware, OBS, default-ROM or release change.3955 remains the graphics
baseline; original-NES speed and pop-free sound remain unproven.

## Mechanism

4041 (`0781da9b83237d4e98c5d65aef0a886e1ce6e21d01ac91a1af4afe6d6234cec3`)
extends rejected4033. At3268 after camera preparation, a replicated12-byte
helper calls existing guarded fast_recover C17954, restores caller flags,
executes the overwritten LDA1CE0 and rejoins the original branch326B. The
returned interrupt-enable policy is deliberately not written to4200. Existing
depth/mapper/pending/beam ownership guards remain. There is no forced update,
busy-wait, original busy-flag bypass or added completed token.

4046 (`40521ef398a2cee6a7edeca12bbcb071c7f2f5591d9447a2704b942a1e680980`)
restores baseline early camera service while retaining the new recovery point.
Its only differences from3955 are the eight recovery hooks/helpers and checksum.
Original graphics and SPC engine bytes are unchanged in both trials.

Six focused tests pass0.219s: exact patch footprints, guarded target/padding
mutations, repeated patch rejection, wrapper flag/stack contract with an
adversarial stub, and rejection of timing gains that worsen either tail. The
wrapper interpreter tests are not an executed full SNES recovery-context proof.

## Measured result

Each trial completed9,090 ordinary frames with a fresh same-core observed run
preserving full primary timeline and native PCM. Every arm retains8,641 sound
packets,1,588 pulse restarts,4,846,034 stereo sample frames,7,342 stable and1,298
excluded intervals. Zero clipped samples does not establish inaudibility of pops.

| Build | Minimum stable gap ms | Maximum ms |
|---|---:|---:|
|3955 baseline|12.147901|20.857717|
|4033 early service removed|9.861696|23.883232|
|4041 new recovery, early service removed|10.078223|23.147823|
|4046 both service points|12.147901|20.927942|

No new variant improves both tails against3955. Do not promote either one.
Audio analysis4044/4049 took29.041/28.496s. Four sampled room populations remain
598/1746/477/847 two-frame game iterations, with no busy-classified interval.
This is not matched original-NES workload speed evidence.

Independent bus/receive analysis4050 compares all198,743 bytes per arm with
zero transfer or source mismatches. All8,641 ordered payloads match3955 exactly
in4033,4041 and4046; a corrupted received-byte mutation fails. Equal payloads
do not establish waveform or onset-time equality.4046 changes12 pictures and
7,709 RAM samples versus3955, with no camera/counter/input/fault differences.

Fresh neutral CPU observation4045 (25.102s replay) confirms that frame2120
sound-driver entry moves156/880→98/814 versus4033. Its return is140/578; the
wrapper rejoins branch326B at160/436 with stack507, matching entry stack507.
Retained game-NMI entry then follows at160/696. The operation really moves
sound before the retained handler; it does not make the driver or transfer
cost disappear. Stack equality alone is not complete register-context proof.

4041 versus3955 retains all20 changed pictures,7,871 RAM samples and one
logical-camera sample; game-NMI/outer-NMI counters, delivered/requested inputs
and adapter-fault trajectories match. No broad graphics/combat campaign was
launched after the audio timing gate failed.

## Next direction

The two location variants establish that a guarded post-preparation call is
possible in the observed window, but neither solves output cadence. Retain
the failures rather than accumulating this overhead in the working baseline.
Separate update-generation time from actual packet/DSP publication time before
another scheduling patch. Any buffering or fixed publication experiment must
prove ordered delivery, no overwritten/lost updates, native audio activity,
onset latency and original game-loop speed—not just smoother interval numbers.
No such protocol change is implemented by this turn.

- [Four-way timing, sound transport and every changed picture](http://127.0.0.1:8766/audio-pre-retained-review-4050/)
- [4041 native audio](http://127.0.0.1:8766/audio-pre-retained-audio-review-4044/)
- [4046 native audio](http://127.0.0.1:8766/audio-dual-boundary-audio-review-4049/)
- [Audio issue6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6)
