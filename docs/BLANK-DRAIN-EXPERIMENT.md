# Forced-blank transition draining

Experimental current candidate: `build/blank-drain-01/native-cpu.sfc`, SHA256
`98616f8db81c8e575121fdbfb6df17f2ba461cacdf2bd84aa180adaa94928605`.
Not deployed to Rival; longer gameplay/audio regression is still required.

New capture telemetry retains transition state and the entire initial-row
requirement bitmap. The unchanged paired-row replay at
`build/row-pair-loading-01/snes` shows 30–36 frame state-2 waits after several
render-on requests, starting with 118–120 required rows. This separates
publication latency from original rendering-off load time; it is not a
claim that every requested row's final contents were already available.

The publisher now enables INIDISP forced blank when transition state is 1
or 2, before touching queued graphics. Only in that state are CHR/row beam
checks bypassed. The 2048-byte budget and bounded scans remain unchanged.
Final OAM/palette publication and screen re-enable still require the normal
final VBlank preflight. Gameplay state 0 retains normal entry/transfer guards.
VRAM access during forced blank is documented in
[SNESdev's PPU memory reference](https://snes.nesdev.org/wiki/Reading_and_writing_PPU_memory).

| Transition | Paired rows | Blank drain | Original NES |
| --- | ---: | ---: | ---: |
| Boot/menu | 186 | 177 | 170 |
| Settings | 67 | 62 | 53 |
| Story | 72 | 64 | 54 |
| Street | 486 | 487 | 459 |

Baseline total 2011 -> 1990. Boot/menu now passes the existing 5% speed
tolerance; the other three speed gates still fail. No tolerance was changed.
Dashboard: `build/blank-drain-quality-01/site/index.html`.

The executed video suite passes. Its late-entry mutation now preserves the
`@on_time` label so the deliberate guard-removal mutant still assembles and
fails at runtime instead of failing assembly due to the new incoming jump.
New case 13 invokes transition publication at scanline 260, checks retirement
of the prepared row while preserving a newer shadow write, and reads back
the transferred VRAM word under forced blank. A mutant explicitly disabling
forced blank during publication fails case 13. Final synthetic BG/OBJ pixels
remain exact. All 108 Python unit tests pass.

The change is experimental: no hardware timing claim, full-game scrolling
verdict, or new audio-fidelity pass. Next required checks include the long
route, bus/ACK and PCM capture, and recovery from blank-to-visible transitions.

## Long-route follow-up

`build/blank-drain-exit-01/snes` completes 7586 frames through café entry,
exit, and room 3. The separate normal-core replay at
`build/blank-drain-exit-normal-01/snes` has byte-identical `timeline.json`
and `audio.wav`, so the observer did not perturb this capture.

The café audit passes all 17380 fixed menu pixels, expected CHR banks and
settled uploads (`build/blank-drain-shop-audit-01/index.html`). The explicit
room-3 `mall_right_03` checkpoint matches camera and scroll registers and
all 20480 fixed-strip pixels (`build/blank-drain-camera-audit-01/index.html`).
These are scoped checkpoints, not full-game equivalence or equal-time
combat benchmarks.

The audio audit verifies 7343 completed packets and acknowledgements against
the length-gated CPU write stream. Full PCM and all multi-frame gap clips
are at `build/blank-drain-exit-audio-audit-01/index.html`. Gap histogram:
1:7318, 2:1, 3:4, 4:5, 6:1, 7:1, 8:1, 9:1, 10:1, 11:4, 22:4, 32:1.
The fixed interior of the mall-entry gap is exactly silent. Do not infer
that every gap is silent: shop-entry raw frames 6068–6079 retain active PCM
(AC RMS 1175.13, peak 2883), which still requires original-game behavioral
comparison. Packet correctness is not a perceptual-popping verdict.

A separate eight-row hidden-transition producer experiment
(`blank-prepare-eight-01`) passed the video suite but increased the baseline
from 1990 to 1992 frames. Boot/settings/story/street became 179/63/65/485
versus 177/62/64/487. It was reverted; the forced-blank candidate remains
unchanged. No hardware deployment.
