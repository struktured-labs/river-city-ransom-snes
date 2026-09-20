# Camera handoff trial restores a missed combat interrupt

Candidate `build/camera-edge-wait-game-3819/native-cpu.sfc`, SHA256
`aaa09580b6aaa8201e022089ccf91e3d51d35d32f15869961a1c73fec9ecec88`.
Parent: 3800. Experimental, not default, deployed, or hardware-qualified.

## Change

A 47-byte helper runs before the existing camera boundary mask. When neither
NMI nor mapper work owns execution and the NMI shadow is enabled, it samples the
beam. Only at lines 232–239 does it wait for the imminent edge before entering
the existing handoff. It also exits if a real interrupt returns after wrap.
It does not enable interrupts, synthesize an interrupt, increment a tick, or
alter original graphic/audio data. All eight game-bank patch sites and the
unused helper region are byte-guarded. A, X and P are restored; no helper
instruction changes the hidden accumulator byte, Y, DB or DP.

Four emitted-code tests cover all 262 scanlines, owned/disabled contexts, return
after frame wrap, and an invalid continuation negative. They pass in 0.004 s.
These instruction tests do not substitute for interrupt-stack/hardware coverage.

## Fresh two-player tests

Four input-only captures (normal/observed for two policies), each 4,930 frames,
preserve exact same-core video/state/input/native PCM. Both ports and both actors'
movement are checked. All report no adapter faults. Busy frames stay counted.

| Stable interval population | Parent 3800 | Trial 3819 |
| --- | --- | --- |
| Sustained attacks | 1,751 × two frames; 1 × three frames | 1,752 × two frames |
| Running/jumping | 1,730 × two frames; 2 × three frames | 1,709 × two frames |

Running/jumping has a changed eligible population; this is not an equal-work
speed ratio. All excluded/censored loops and strict-phase failures remain in
JSON. The report is not a whole-game or matched-original-NES speed pass.

[Trial pictures and native episode audio](http://127.0.0.1:8766/camera-edge-combat-review-3823/)
· [Parent failure](http://127.0.0.1:8766/palette-combat-review-3817/).
The trial page was browser-rendered and visually inspected.

## Actual missing event recovered

Instruction control 3821 and observed 3822 preserve the complete 4,930-frame
primary timeline and native PCM. The pinned 1837–1840 window now contains a
native NMI and original sound-driver return in every frame. Parent 3800 is the
real negative: no native NMI in 1838 and no sound-driver return in 1839.

Parent sound-return gap: 725,724 master clocks (about 33.8 ms).
Trial: 368,446 then 366,646 clocks (about 17.2 and 17.1 ms).
The first sustained loop's next start moves from frame 1840 to frame 1839.
No waveform filtering, normalization, input retiming or observation masking.
This fixes the measured missed service; it does not establish pop-free sound.

[Bound before/after instruction events](http://127.0.0.1:8766/camera-edge-recovery-3825/report.json).

## Fresh graphics and menu qualification

The ordinary 9,090-frame route 3824 completes with no reported faults. New
controls/observations qualify this exact cartridge, not inherited parent flags:

- DMA control 3826 and observer 3829 preserve every frame and native PCM;
  the unobserved observer core also reproduces the primary core. Audit 3832:
  51,974 general DMA transfers (1,922 forced blank, 50,048 VBlank, four other),
  no unsafe envelopes, latest visible completion line 258. Active-scanout,
  crossed-frame and unfinished-transfer negative controls are rejected.
- Renderer control 3827 and observer 3830 preserve every frame/native PCM.
  Audit 3833: 7,473 eligible gameplay frames and 6,502 held-camera checks,
  no incomplete coverage, split scrolling, or stale-camera failures.
- Input-only pause/status capture 3828 passes original-reference numeric tiles,
  own-RAM values and fixed-region pixels at opening and reopening, with zero
  mismatched pixels in either phase (3831). This is not every-menu qualification.
- Palette observer 3836 preserves its exact same-core control 3835, which
  separately matches primary-core prefix 3834. All 2,579 frames retain original
  and prepared palette equality to baseline 3695. The known delayed fade in
  3780 still fails the negative gate; 3819 has no late physical-CGRAM differences
  and retains the eleven earlier color updates (3837). Frame-boundary snapshots
  do not establish per-scanline or full-route palette freshness.

[DMA audit](http://127.0.0.1:8766/camera-edge-dma-review-3832/) ·
[Actual rendered scrolling](http://127.0.0.1:8766/camera-edge-renderer-review-3833/) ·
[Present Status pictures](http://127.0.0.1:8766/camera-edge-status-review-3831/) ·
[Palette comparison](http://127.0.0.1:8766/camera-edge-palette-review-3837/).

The two earlier target HUD pictures at frames 2473/2485 still match parent3800.
Prefix game-counter/requested/delivered-input differences are zero; ten picture
differences remain. These descriptive parent comparisons do not certify every
graphic. Fresh ordinary prefix replay: 7.419 s; observed CGRAM replay: 8.330 s.
Fifteen edge/combat/controller tests pass in 0.075 s.

## Scope still open

Full-route palette/HUD freshness, broader interrupt-context and menu coverage,
matched-original-NES heavy-combat speed, pop-free audio, HDMA/physical per-byte
timing and hardware acceptance remain open. No MiSTer, EverDrive or SNES Junior
deployment occurred.
