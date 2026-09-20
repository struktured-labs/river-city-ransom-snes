# OAM word-copy speed candidate

The guarded [PPU-ring candidate](PARK-RING-INTERRUPT-EXPERIMENT.md) still had
six late park audio packets. The next measured cost was the original OAM page
snapshot. The new candidate copies low-WRAM pages with 128 native direct-page
word loads and long WRAM stores. Pages outside the bank-zero WRAM mirror retain
the existing explicit-bank MVN fallback. No graphics, game logic, music data,
or controller layout changes are involved.

Candidate `build/oam-word-native-200/native-cpu.sfc` SHA-256:
`d88604f5a2e473e4154e59ac6e5caf88d52de2d2590c033b543274222681b84d`.
Parent 192:
`5ac817a86c27c657d0dac9bf3d09677ea87057cee597c2184647e62f3abfccc5`.
Only `experimental_oam_word_copy` is newly enabled relative to that parent.
It remains **off by default**. Rebuilding the parent with the current sources
and this flag off (`build/oam-word-default-control-205`) is byte-identical.

## Executed adapter and timing oracles

[34 source pages and three negative controls](../build/oam-word-fastrom-oracle-203/report.json)
pass. Every source page 00..1F is exercised, including the active stack (01),
self-copy (10), adapter state (1C) and mirror boundary (1F); pages 20 and FF
exercise fallback. All 256 destination bytes and caller A/X/Y/DB/D are checked.
The copy adds no stack pushes, important when the source is the active stack.
Missing a word, reading the wrong word, and allowing page 20 into the direct-page
path each fail the actual emulated adapter case 6.

[FastROM copy timing](../build/oam-word-fastrom-timing-203/report.json):
MVN 12,310 versus word copy 9,176 master clocks, saving 3,134 clocks for the
synthetic page-02 entry-to-copy-complete span. These elapsed clocks include
intervening emulated events; this is **not a whole-game speedup percentage**.
Observer and normal-core runs have identical complete 128 KiB WRAM per arm.

## Gameplay evidence

- [Park packet timing](../build/park-oam-word-execution-200/index.html):
  all three gates pass; zero stable unpaused park packet intervals over the
  unchanged 1.5-frame limit, down from six in the guarded parent.
- [Interrupt timing and observer neutrality](../build/oam-word-neutral-span-audit-206/index.html):
  zero late NMI-entry intervals in the 7535..8105 profile window. The complete
  9,407-frame timeline and WAV match a fresh normal-core run byte-for-byte.
- [Straight-right movement](../build/oam-word-movement-audit-204/index.html):
  same 21-pixel displacement, no later first arrivals than the original NES.
  This is a 32-frame stationary-camera check, not full-game speed parity.
- [Repeat café purchases](../build/oam-word-repeat-audit-204/index.html),
  [YES/NO](../build/oam-word-no-audit-204/index.html), and
  [Present Status](../build/oam-word-status-audit-204/index.html) pass the original
  fixed-region pixel and RAM-value checks. State-aware café navigation uses
  ordinary controller input; independently evolving encounters are not aligned
  into a speed comparison. The known old stale-cursor ROM is still rejected.
- [Pause checkpoints](../build/oam-word-pause-audit-204/index.html) and
  [every closing frame](../build/oam-word-pause-motion-204/index.html) remain
  **FAIL**: closing reaches permanent blank at input offset 50 versus NES 49.
  Other eight checkpoints pass, including cursor clearing and re-entry.
  The old live gameplay parent also differs in some early closing frames.

Zero missed packet deadlines in this replay does not establish clean physical
audio, all encounter seeds, scrolling coverage, or original-speed full-game
parity. Those remain open. The pause discrepancy is not hidden with a lag search
or a relaxed pixel threshold.

## Splash integration and boot-monitor correction

[Branded integration](../build/oam-word-branding-audit-205/index.html) passes all
eight gates, including reveal/hold/teardown negative controls, continuous bass
glide/fade, and the original menu after handoff. Branded ROM SHA-256:
`765052c798c269aca48162d9242c5ec2b4eabb49ef95efb7bc0f0f677658c05f`.
This retains the existing four-second sound/hold and 48-frame fade.

First gameplay captures of that exact branded ROM exposed a harness bug:
frames 121..308 interpreted uninitialized adapter RAM (`55` bytes) as game
faults while the splash still owned the CPU. Those failed captures are retained
as `build/oam-word-branded-{movement,status,park}-206`; the status run also
omitted the required full-RAM flag and was correctly rejected.

`tools/boot_faults.py` authenticates the declared splash ROM and exact reset/
D1 entry bytes. Raw fault registers are now retained for branded runs. A
one-way CPU-bank handoff activates game checks immediately upon leaving D1;
re-entering D1 cannot turn checking off. The verifier replays this policy from
the saved CPU and raw register observations and binds the copied build manifest.
It rejects missing handoff, exemptions outside preboot, disabled checking after
handoff, and hidden faults. There is no longer an arbitrary 120-frame grace
period for these branded builds. Existing unbranded timelines are unchanged.
Eight focused tests pass; complete Python suite: **340 tests**.

Fresh branded captures pass [movement](../build/oam-word-branded-movement-audit-207/index.html),
[status](../build/oam-word-branded-status-audit-207/index.html), and
[park packet timing](../build/oam-word-branded-park-audit-207/index.html).
The latter runs 9,712 frames with zero stable unpaused park deadline misses.
The corrected movement capture retains exactly the same CPU, game RAM, input,
video and audio observations as its failed-monitor predecessor; only the
classification of preboot adapter telemetry changed. Game checking activates
at frame 309 and never deactivates.

## Rival deployment and actual audio

Rival restarted at **23:18:14 EDT on September 16, 2026**, launching
`/media/fat/RCR-SNES-765052c.mgl`. The remote ROM hash matches the branded SHA
above; the MiSTer process reports that MGL and the pinned SNES 20260603 core.
Previous `8bcff69` ROM/MGL remain available; no files were deleted.

[Review dashboard](../build/oam-word-review-208/index.html), also available while
the loopback evidence server runs at
<http://127.0.0.1:8766/oam-word-review-208/>. It serves review formats only,
without ROM downloads or directory listings.

[Physical boot-audio audit](../build/oam-word-hardware-208/audio-audit/index.html)
passes all eight gates. Maximum pitch error across twelve glide checkpoints:
1.323%; final/initial half-second RMS ratio: 0.3597; maximum ident sample step:
332; resumed game-music RMS: 376.15. Source is the existing Blackmage DeckLink
recording `20260916_214537_struktured_v6c_part2.mkv`, audio stream 0:a:0,
seconds 5550..5577, decoded as 16 kHz mono PCM. Bass onset: 5560.01 seconds.
The screenshot at recording second 5561 shows the full logo; the later live
screenshot shows 1P selected. No gameplay input was injected.

OBS observations immediately before deployment and after boot show live,
unmuted Blackmagic audio and muted desktop/microphone. They are timestamped
observations, not a claim of continuously logged historical settings. Recording,
replay, scene and mute settings were not changed. Full recording remains active
and mutable; extracted WAV/screenshots and provenance are individually hashed.

The physical pass certifies this boot cue and audio handoff, **not every
gameplay pop, perceived bass timbre, or full-speed encounter**. Pause-closing
timing and broader goal remain open. Controller presets are not enabled.

## Reproduce the low-level checks

```sh
python3 tools/check_oam_word_copy.py --fastrom \
  --core .deps/snes9x/libretro/snes9x_libretro.so --out build/oam-oracle-new
python3 tools/check_oam_copy_timing.py \
  --core .deps/snes9x/libretro/rcr_span_ack_libretro.so \
  --control-core .deps/snes9x/libretro/snes9x_libretro.so \
  --out build/oam-timing-new
python3 -m unittest discover -s tests -q
```
