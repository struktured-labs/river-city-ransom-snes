# Cycle-balanced pulse pitch update

September 18, 2026. At the end of this emulator investigation the experiment
was **not deployed** and Rival remained on `339d2b220a3a`. The subsequent
[Rival deployment and physical trial](BALANCED-PITCH-RIVAL.md) now document
the candidate on hardware, with remaining audio limitations retained.

[Actual DSP samples and native A/B audio](http://127.0.0.1:8766/balanced-pitch-review-1509/).

## Implemented improvement

The old publisher writes low pitch before fetching high, leaving a 17-SPC-clock
window for the DSP to read an intermediate value. The new sequence prefetches
high into X, fetches low into A, writes low, increments the DSP address, then
writes high. The gap becomes eight clocks; this is still not atomic.

The first same-size trial1480 costs one additional clock per active voice.
Its 50,265 executed state cases, delayed-transfer clocks and game transport
pass, but room fades fail (first scenery 8/6/7 versus NES 7/7/7). Failed
collages1491 are retained. It was not promoted.

Balanced trial1493 also rewrites the pointer calculation: copy high to DP69,
shift low in A, rotate DP69 through carry, then add the table base. This saves
seven clocks. Two harmless direct-page reads restore six clocks, offsetting
the one-clock prefetch cost. Actual executed calls verify **unchanged total
cost**, not just a hand-counted estimate.

Only two checked 40-byte SPC regions and the cartridge checksum can change.
There is no new helper, upload space, stack storage or sample. Receiver polling
and post-publication KON remain intact. X/Y are scratch (high pitch/zero);
the immediately following verified instruction reloads A and N/Z. Broader
caller coverage remains important.

Candidate: `build/balanced-pitch-1493/game/native-cpu.sfc`, SHA256
`777635fa6d8647911536e9ef0ca9025fc4e04a78ed11200dfc36cd29ae4e565b`.

## Executed audio evidence

Both current and balanced engines replay the same 2,512-packet fixture. It
preserves publication frames, not original within-frame CPU work. Observers
are neutral against fresh normal captures; raw DAC equals delivered PCM.
All 3,482,203 pulse samples are reconstructed from DSP writes and latch phases.

| Same 13,203 pitch transactions | Current engine | Balanced trial |
| --- | ---: | ---: |
| Split-byte intermediate-pitch samples | 122 | 51 |
| Split samples with nonzero voice contribution | 37 | 19 |
| Wrong first pitch after eligible restart | 0 | 0 |

Transaction keys and high-byte completion times match. Residual intermediate
values remain; nonzero contribution is **not** an audible-click count. No
perceptual or physical improvement is claimed yet.

Executed checks cover 50,265 cases: every 11-bit period, both voices, six sweep
controls and both enable states, all constant/envelope levels and 25 two-voice
boundary combinations. DP/final DSP state and call costs match. A wrong-high
mutation fails 4,082 cases. Sixteen real-engine continuous-clock tests cover
two frame modes and four sender delays; all pass.

## Full-game timing and graphics

Fresh normal1494, DSP1497, main1503 and renderer1504 complete 9,406 frames;
each observer preserves its corresponding normal capture. Every video, RAM,
input, NMI and native-state field matches the previous cartridge. The sparse
main instruction trace also matches byte-for-byte.

- All three room fades match at all forty fixed offsets; first scenery is
  7/7/7. Total-load gates pass too.
- 3,823 stable main iterations retain two-tick cadence. Qualified park camera
  holds have no short irregular intervals; fourteen-frame stops remain.
- All 7,785 eligible renderer frames have full coverage, no split scroll and
  no stale held-camera failures.
- All 8,950 actual audio packets and 1,638 restart orderings pass.
- All 379,784 DSP commands retain register, value and order. Exactly 47,588
  normal low-pitch writes move nine clocks later; every other write remains
  at its original clock. Full receipt and ready records match.

## Strict failure retained: callback boundaries

Checker1505 requires exact emulator callback sample counts and reports **FAIL**,
despite passing state/cost checks. Two adjacent pairs redistribute one sample:

| Frames | Original lengths | Candidate lengths |
| --- | --- | --- |
| 2382 / 2383 | 533 / 534 | 534 / 533 |
| 6341 / 6342 | 534 / 533 | 533 / 534 |

Audit1508 retains these differences and verifies clock-level evidence. Each raw
DAC stream equals its concatenated WAV; both contain 5,014,500 stereo samples;
all packet/ready clocks match. There is no lost sample in that concatenation.
The strict result is not rewritten as a pass; no audio is retimed.

DSP attempt1487 incorrectly used the normal core and failed on missing traces;
it is not qualified evidence. Fresh1492/1497 use the bound observer core.
Initialization/splash pitch writes (10/20/21-clock pairs) remain unchanged.

## Remaining work

All 18 review artifacts and both full room-entry collage directories were
fetched over HTTP and hash-checked. All six listening clips equal their source
PCM slices exactly. A read-only Rival check still finds the previous hash-named
cartridge and unchanged saved SNES configuration.

This is a cheaper partial fix for pitch-update artifacts, not a resolution of
physical popping, capture discontinuities or the recorded 17ms gap. Hardware
comparison and broader game/audio coverage remain necessary. Splash sound,
graphics and controls are unchanged. Original-speed and full-game scrolling/
audio fidelity requirements remain open.
