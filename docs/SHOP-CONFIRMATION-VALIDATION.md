# Café YES/NO and corrected MiSTer build

The player reported that the café's YES/NO choice was blank. The old check
covered only the first item list. A new controller-only
`traversal-shop-confirm` capture selects one item, releases the button, and
observes the prompt at three fixed checkpoints on original NES and SNES.

Original NES CIRAM acquires the six glyph bytes `BB D8 C4 D2 CD CE` at
physical offsets `$02CE–$02D1,$02D9–$02DA`. The previous port leaves all six
bytes zero. The separately replayed original FCEUX trace at
`build/reference-shop-confirm-x11-79` identifies **ten newly executed direct
hardware accesses** at PRG offsets `$9634,$9639,$963E,$9643,$9648,$964D,
$9652,$9657,$965C,$9661`: four `$2006` address writes and six `$2007` glyph
writes. They were absent from the earlier, shorter shop execution trace.
The trace is bound to `build/shop-confirm-shadow-nes-77`'s verified original
ROM, controller inputs, and palette. The FCEUmm observer patch now also
exposes the original physical CIRAM read-only through the standard diagnostic
video-memory pointer; this does not change PPU behavior.

Rebuilding with that trace adds those ten hooks (242 → 252; still 44 shared
stubs). No hand-painted text or original-art changes. ROM SHA-256:
`fa33efb584a40278f8b079cfba8a5b4c09ad38ac26786154e582a0f5608dbbd8`.
The detailed [three-way browser audit](../build/shop-confirm-audit-80/index.html)
compares original NES, missing-text port, and corrected port at the fixed
rectangle `(108,170)-(225,188)`, across all three checkpoints. The old port
differs at 113 prompt pixels; the new port differs at **zero** and its CIRAM
shadow and SNES VRAM contain the original six glyphs. The negative control
must fail for the audit to pass.

The [candidate route-equivalence audit](../build/shop-confirm-route-equivalence-audit-83/index.html)
permits exactly the ten new three-byte hooks and four checksum bytes: 34 ROM
bytes changed in a 2 MiB image. Against the previous ROM, the full existing
7,540-frame shop-exit route has identical per-frame video hashes, complete
game-RAM hashes, controller delivery, audio callback metrics, and **identical
WAV bytes**, with no adapter faults. Since that route never selects an item,
this is a scope-limited non-regression proof, not evidence that every shop or
purchase works. The independent 24-frame rightward movement check still
matches the NES's 21-pixel displacement, without positive arrival delays.

For the corrected ROM's 7,540-frame route, 7,274 CPU/SPC packets match the
CPU audio writes and all 7,274 have acknowledged completion; 838 scheduled
key-on writes match, with no mismatch or unflushed CPU writes. Every captured
audio callback is positive and contiguous, no PCM sample clips, and maximum
step `0.126770` of full scale stays below the original NES isolated-reset
reference limit `0.171656`. See
`build/shop-confirm-shop-exit-transient-audit-83/index.html`. Those are
digital transport/discontinuity gates, not proof of subjective sound quality.

After the first café purchase the user found a second regression: the
YES/NO glyphs remained onscreen and obscured the next purchase. The
`traversal-shop-repeat` route now makes **two purchases without leaving the
café**, with released input and independent checkpoints. Original NES FCEUX
execution at `build/reference-shop-repeat-x11-89` identified 17 additional
direct `$2006/$2007` accesses. The second build adds only those exact hooks
(252 → 269, still 44 shared stubs), without modifying art or SPC code.
SHA-256: `59bd61c978077e29581aa78d13f8cf52c6239894ae01675b603a9493876cacfe`.

The [two-purchase browser collage](../build/shop-repeat-audit-91/index.html)
compares the original NES, deliberately broken predecessor, and corrected
SNES at ten stages. The six original CIRAM glyphs clear on both purchases,
return for the second confirmation, and match SNES shadow, actual VRAM,
and every fixed-region image pixel at every stage. The old ROM leaves 113
wrong prompt pixels after each purchase and must fail. Money falls from
`$20.00` to `$19.05` to `$18.10` in the matching NES/SNES images. The
[patch-scope and route audit](../build/shop-repeat-candidate-audit-92/index.html)
permits exactly 17 new three-byte hooks and four checksum bytes (55 bytes
total). All 7,540 previous no-purchase frames retain identical video, game
RAM, controller events, audio callbacks and complete audio WAV bytes.

The first two-purchase shop-fixed ROM was on Rivalmage as `RCR-SNES-59bd61c.mgl`.
OBS confirms live video. The earlier
[hardware-capture probe](../build/shop-confirm-hardware-audio-audit-86/index.html)
found zero samples in those *older* recordings, not proof of a silent cartridge.
The later [Rivalmage/DeckLink audit](../build/branding-ident-growl-audit-139/hardware-audio/index.html)
detects the splash's original bass notes and resumed game music in an active
Blackmage recording. That resolves the recording-path uncertainty for this
session; full-game SFX/music quality and performance remain separate open gates.

The later no-choice visual fix and pause-menu stale-cursor fix were independently
checked against NES and the previous cartridge in the
[pause-route audit](../build/pause-cursor-candidate-audit-122/index.html).
It includes the two-purchase and choice-NO checks and whole-route frame,
RAM and WAV equivalence outside the patched instructions. The current
Rivalmage ROM is the branding/audio-enabled version of that pause/shop candidate:
`RCR-SNES-a501f70.mgl`; see [splash validation](BRANDING-SPLASH.md).
The intro intentionally adds boot time but does not change gameplay speed.
