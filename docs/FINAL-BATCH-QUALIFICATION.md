# Current build: menus, dense timing, and native audio isolation

Candidate 3032 is unchanged:
`a38458515709e0048b5d5b6e5e6ca58888cd3151ea7d839741468f6c106398ba`.
No Rivalmage, Bluemage, controller, OBS or saved-setting access occurred.

[Menu collages and combined qualification](http://127.0.0.1:8766/final-batch-qualification-3060/)
and [native audio edges/stems/DSP context](http://127.0.0.1:8766/final-batch-audio-edges-3058/).

The preceding turn fixed the sprite-publication mismatch while retaining the
recorded combat pass. This turn adds new executed coverage, not a ROM revision.
The complete speed/scroll/audio goal remains open; neither a release nor a
pop-free verdict is claimed.

## Menus on this exact cartridge

Fresh captures 3046–3049 total 19,990 frames:

| Original-NES oracle | Frames | Result |
| --- | ---: | --- |
| Present Status opening/reopening | 2,537 | PASS; all fixed-region digits/pixels |
| Pause selector exit/reopen | 2,285 | PASS; cursor pixels/VRAM |
| Two consecutive café purchases | 7,821 | PASS; repeated prompt lifecycle |
| YES/NO movement and confirming NO | 7,347 | PASS; cursor and unchanged money |

Audits 3050–3053 reuse the original fixed references and known-broken controls.
`review_phase_balance.menus` independently recomputes the results; stale cursor
and stuck shop-prompt controls still fail. Full screenshots are context, not
claims that enemy positions outside the fixed menu regions match across systems.

## Expanded final-batch margin

The original 18-case boundary fixture had palette preview ineligible. New
fixture 3054 enables rendering, seeds nontrivial original/shadow/cached palette
data, activates the actual production palette converter, poisons physical OAM,
and reads back all 544 OAM bytes and complete CGRAM. Independent RGB555 values
come from the actual cartridge palette table; original palette state/cache and
unconsumed row ownership must remain intact.

156 cases vary target lines 248–251, 13 NOP delays, preview eligibility and
transition state. The guard's own sampled scanline is read from DP scratch,
not inferred from the requested target line. 60 cases are admitted and 32
execute palette conversion. The original cutoff is an executed negative
control. Follow-up 3055 sweeps every integer NOP delay 0–255 at targets 249/250,
with conversion active and state0/2: **1,024 cases, zero failures**.

**Important:** expensive converted palettes finish as late as line **261**,
not the earlier empty-palette fixture's 257. No sampled overrun occurs, and
physical OAM/CGRAM remain correct. This is a tighter timing margin, not an
exhaustive proof for every queue/fade state, subline phase or physical core.
The fixture covers the actual final batch, not the entire native NMI call graph.

## Current audio: actual contributions and cadence

Fresh noise-only and all-but-noise captures 3056/3057 use the same core as DSP
capture 3039 and query every requested voice option after ROM load. All 9,248
non-audio timeline rows, original game RAM, images, inputs and sample boundaries
match the full mix. Both stems are non-silent and reconstruct the entire native
mix within measured integer-rounding residuals of 0 or 1.

Review 3058 selects the 12 strongest gameplay sample steps separated by at
least half a second. Every stem is measured at the **same sample/channel**
selected by the full mix. Noise contributes the larger step in **6/12** cases;
the remaining voices dominate the other six. Largest example: frame7897,
step+4578 = noise+2724 and rest+1855 with a one-unit rounding difference.
Frame1969's +3296 step instead has noise+1055 and rest+2241.

This does not classify any selected edge as a defective pop: natural NES
pulse/noise edges can be sharp. It does show that noise-only attenuation or a
noise-only synthesis fix cannot be credited with addressing all these selected
edges. The remaining voices and update timing need separate investigation.

Actual consecutive SPC-completion ticks yield 7,609 intervals with gameplay
task active and no transition-state flag. Pause and original-NMI-busy states
are not filtered. Native DAC-sample units: minimum376.625, median530.25,
99th percentile621.59125, maximum677.5. At32,040Hz this is approximately
11.75–21.15ms. These are observed completion intervals, not proof of a missing
packet, perceptual stutter, original-NES timing equivalence or its cause.

The review includes nearby exact-clock DSP writes, screenshots, common-scale
waveforms and 36 byte-checked native one-second excerpts. No gain, resampling,
normalization, fitted time shift or waveform phase alignment is applied.
Corrupting a stem fails reconstruction; an empty gameplay eligibility mask
produces no events rather than a false clean-audio verdict.

## Verification and next action

1,243 unit tests pass (`/tmp/rcr-tests-3059.log`); `git diff --check` passes.
Audio review:817 source bindings/49 artifacts. Combined review:7,347 source
bindings/9 artifacts, including the freshly revalidated menu oracles and all
dense executed fixture ROM/RAM receipts. Every published audio slice was
compared to its native source samples; both pages were inspected in Chromium.

Next, isolate the remaining pulse/triangle contributions at these frozen
events and distinguish original sound-driver update timing from CPU transfer
and SPC synthesis timing before changing audio scheduling. Retain the current
speed, scrolling, menu and DMA checks for any candidate change. Hardware
qualification remains outstanding, with Bluemage permitted and Rivalmage
off-limits while occupied.
