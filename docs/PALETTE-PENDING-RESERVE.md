# Conditional palette reserve: candidate 3800

Cartridge: `build/palette-reserve-absolute-game-3800/native-cpu.sfc`.
SHA256: `6a01aa4269338cc90098fce914dd65c09b1f0618ea57c28e8de2549449c4d33e`.
Experimental, not deployed or validated on EverDrive / SNES Junior.

## Actual displayed palette, not just safe DMA

The prior full-route transfer-count diagnostic could not tell whether omitted
palette transfers delayed a changed color. A source-built read-only CGRAM query
now observes all 512 physical palette bytes after each emulated frame, together
with original shadow and prepared palette data. Its unobserved run reproduces
the parent core's full primary timeline and native PCM. Observer-on/off runs
then reproduce those outputs on the exact same new core and cartridge.

Across the 2,579-frame prefix, baseline 3695 and prior 3780 have identical
original and prepared palette data. At frame 1203, however, 3780 leaves eleven
colors one frame behind, visibly darkening the street fade. At frames 2437 and
2441 it publishes eleven colors earlier than 3695. Neither finding is hidden
by aggregate DMA safety or a favorable screenshot selection.

3800 reserves more time for the final palette batch only when original flag
`$003E` bit 3 reports a pending palette update. The row admission bound becomes
249 instead of 252 in that case; the final valid window remains 240–253.
Hardware blanking checks and the existing forced-blank success continuation
remain intact. No new dirty flag, graphic data, or palette contents are introduced.

The first emitted experiment 3798 incorrectly used direct-page addressing for
the flag while the CPU's direct page is relocated. It is retained as a failing
negative, not a qualified build. 3800 uses the verified absolute load. Emitted
code tests cover all 256 flag values against all 256 low scanline values.

The new prefix audit rejects 3780's delayed colors. 3800 removes that regression
and preserves the two earlier updates, with no changed original/prepared stages.
The two targeted HUD pictures also remain correct. All other picture differences
are retained; this is not whole-picture equality with 3695 or original-NES timing.

- [Palette comparisons and every classified color difference](http://127.0.0.1:8766/cgram-publication-review-3805/)
- [Native audio and all short-route picture differences](http://127.0.0.1:8766/palette-reserve-audio-review-3807/)
- [Publication issue #18](https://github.com/struktured-labs/river-city-ransom-snes/issues/18)
- [Audio issue #6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6)

## Current measured scope

Ten CGRAM/core/emitted-palette-helper tests pass (rerun: 0.056 seconds).
Fresh short observed palette capture: 9.534 seconds; short observed audio replay:
7.090 seconds, 7.643 seconds including finalization. These are replay measurements,
not a promise about complete iteration time.

The 9,090-frame ordinary traversal/shop/park route 3806 completes with no reported
adapter faults. This alone does not qualify actual transfer envelopes or scrolling.

Fresh full-route qualification now also passes on this exact cartridge:

- DMA control 3808 reproduces the primary core. Observed 3811 reproduces its
  exact same-core control across every primary frame and native PCM sample.
  Audit 3813 checks 52,090 general DMA transfers: 1,942 forced blank, 50,144
  VBlank, four other, with zero unsafe envelopes. Latest visible completion is
  scanline 259. Deliberate active-scanout, crossed-frame and unfinished transfers
  are rejected. HDMA and physical per-byte behavior remain outside this test.
- Renderer control 3809 and observed 3810 have identical full timelines and
  native PCM. Audit 3812 covers 7,473 eligible gameplay frames and 6,502 held-camera
  checks: zero coverage failures, split scrolling or stale-camera failures.
  This does not certify tile contents, all encounters or original-game speed.

[DMA evidence](http://127.0.0.1:8766/palette-reserve-dma-review-3813/) ·
[Renderer evidence](http://127.0.0.1:8766/palette-reserve-renderer-review-3812/).

Short native-audio capture 3804 is neutral after process-exit finalization:
2,179 sound packets, no clipped samples. The targeted sound-driver return gap
improves from 23.617 to 18.689 ms. Stable completion intervals are
11.190–22.159 ms versus the baseline's 9.852–23.707 ms. Untouched native clips are
retained; no claim of hearing them, waveform equivalence, or pop-free playback.

Full-route palette freshness, original-speed matched heavy combat, wider menu
coverage, and physical audio/graphics acceptance remain open. A frame-boundary
CGRAM observation is not a per-scanline palette-timing measurement.
