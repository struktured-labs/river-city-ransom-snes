# Executed correction for the offline hybrid-noise attack

[Before/after native clips and proof3128](http://127.0.0.1:8766/noise-source-first-review-3128/).
The current game cartridge3065 and its SPC engine remain unchanged. Neither
MiSTer nor OBS was accessed. This repairs an experimental synthesis path, not
an established cause of the user's physical popping.

## Actual engine change

The [previous bit-hold experiment](NOISE-INTERPOLATION-CONTROL.md) exposed two
sample frames from the wrong source at two fallback-noise attacks. Its helper
published nonzero volume before selecting the source/pitch.

`build_noise_source_first.py` authenticates the exact2x/8x prototype against
the original current-engine image, then replaces a three-byte entry at file
offset`$323` with a jump to a48-byte helper at free offset`$31E0` (SPC`$35E0`).
The helper branches on the already-computed final volume:

- Nonzero: save volume, configure source/pitch, restore and publish volume.
- Zero: publish zero on both channels, then configure source/pitch.

The zero path matters: selecting a new source at the old nonzero volume before
muting would introduce a different transient. Both paths return to the original
main loop at`$0471`. Samples, loop layout, upload size and command stream stay
unchanged. The builder verifies the complete engine, hook preimage, free helper
padding and embedded cartridge image before applying the patch.

Fixtures3118/3119 are the corrected2x/8x versions. Each still uploads52,224 bytes
and retains the deliberately shortened8,192-bit noise sequence. They are not
production candidates.

## Executed held-case regression

Fresh normal captures3120/3121 and observed captures3122/3123 each execute all
2,220 packets. Within each arm, complete PCM, RAM, image and received bytes
match its same-core control; raw DSP output equals the native WAV. Both pulse
restart controls retain correct initial pitch and no stale nonzero onset.

Across the2x/8x corrected arms, all packet/callback timing is identical. Both
pulse-only cases and **all eight fallback-noise cases now match sample-exactly**,
including the two period2 attacks that previously differed. No gain adjustment,
resampling or waveform alignment is applied.

The new auditor checks source and BRR pitch at each actual nonzero volume write,
not only final registers at packet-ready. Each corrected engine passes1,792
held noise packets and3,584 nonzero volume writes with zero ordering violations.
Expected completed source/pitch/volume/GAIN values also pass.

The two unchanged old engines are reloaded as executed negative controls, not
synthetically edited traces. Each has**44 ordering violations**: the test now
also catches new BRR periods becoming audible before their pitch is updated,
not just the initially noticed fallback attacks. Both old engines are rejected.

## Separate enabled-zero source transitions

The original held test used channel disable between cases, bypassing the new
zero-volume branch. Fixture3124 explicitly keeps noise enabled (`$4015=8`) and
issues constant-volume-zero commands while changing source selection:

1. BRR period6, volume15.
2. Built-in noise period2, volume0.
3. Built-in noise period2, volume15.
4. BRR period6, volume0.
5. BRR period6, volume15.

Normal3125 and observed3126 execute268 packets, including the two pulse controls
and final disabled tail. Actual receiver bytes, raw DAC and same-core neutrality
pass. All64 enabled-noise packets pass source/volume ordering, including16
zero-volume packets. At each zero-command source write, both DSP volumes are
already zero. The seven subsequent complete frames of each muted case are
exactly silent. The first transition frame remains in the full recording and
is not mislabeled as a wholly silent frame.

This does not certify uninterrupted audible cross-source transitions or every
DSP internal pitch-latch phase. That broader qualification remains open.

## Verification and limits

Five new tests cover the two emitted SPC paths, guarded engine/padding rejection,
source/pitch-before-volume checks, missing publication, both-channel mute order
and actual enabled-zero stimulus bytes. Full suite: **1,271 tests pass**;
`git diff --check` passes. Combined report3128 has170 checked source bindings,
nine artifacts and eight independently verified exact native excerpts. Its web
page was opened and visually inspected.

The correction removes the observed prototype attack failure. It does not waive
the shortened LFSR cycle,73-frame upload penalty, seven retained spectral
regressions from the earlier experiment, or full-mix/gameplay/hardware tests.
The repaired engine's spectrum is not newly certified by this attack audit.

Next work must address those representation/timing costs or keep the current
built-in-noise engine. Physical pop attribution still needs a known Bluemage
capture path; Rivalmage remains off-limits. No hardware deployment or full-goal
completion is claimed.
