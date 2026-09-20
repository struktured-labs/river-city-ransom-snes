# Retained interrupt return and late camera publication

Follow-up: [deterministic SPC hardware replay](DETERMINISTIC-SPC-HARDWARE-REPLAY.md)
adds identical-command Rival/emulator audio tests and native comparison clips.
It does not clear short pops or establish a new game release.

September 18, 2026. Candidate `0956bd97b78f` is now running on Rival after
bounded boot and gameplay recordings. The speed/scrolling/audio goal remains
open. [Review: real frames, native audio, hardware video and all limits](http://127.0.0.1:8766/retained-camera-review-1222/).

## Change

The previous sweep-driver integration lost two physical frame starts. Its
retained game interrupt returned during a fresh VBlank, then the ordinary
epilogue waited for VBlank to end before re-enabling NMI. The fresh event was
therefore missed. Historical instruction evidence is in
`build/sweep-driver-lost-edge-1132/` and `LIVE-SWEEP-DRIVER.md`.

`snes/nmi_return_tail.inc` identifies only the saved
`camera_deferred_nmi_return` continuation and skips that wait on this path.
Ordinary returns retain the wait policy. No new WRAM latch is needed. The
lookup uses an eight-bit X index into page one so the emulation stack wraps
correctly. An initial stack-relative prototype failed at stack positions
0–3; the executed all-stack-position test caught it before deployment.

Ordinary returns are not cycle-identical: the extra continuation check can
cross a VBlank edge. The line239+40NOP fixture records one such old/new event
count difference explicitly. It is not excluded or called identical timing.

The recovered late NMI exposed a separate camera lag: candidate1149's room0,
camera266 sample rendered the previous position, causing 5,004 expanded-band
pixel differences. `native_video.asm` now makes a camera-only late commit:
four WRAM stores update the two street HDMA entries, with no VRAM/OAM/CGRAM
DMA or queue consumption. It is gated to visible gameplay, no transition,
and entry lines243–261 or0–28, before street HDMA begins at32. On-time and
transition DMA guards remain intact. The option is passed to both the boot
publisher and runtime assembly.

`--experimental-retained-return-edge` remains off by default, requires the
deferred-NMI/re-enable/late-prepare guards, and is recorded in the manifest.
Disabled rebuild1221 is byte-identical to native1119. Game graphics, controller
mapping and splash assets are unchanged.

## Executed qualification

- NMI fixture1166: 280 cases, including all256 stack positions; 24 old-code
  controls; three executed damaged variants caught. Actual hardware registers,
  interrupt entry, production return tail and complete production publisher.
  A/X/Y/P/stack/depth and late queue ownership checked. The original game-NMI
  body is not included in this synthetic fixture.
- Camera fixture1174: 40 full-publisher cases and eight executed damaged
  variants caught. Includes beam0/28/29/239–243/250/256/260/261, delayed wrap,
  task/transition guards, both HDMA entries, adjacent descriptors, real2KiB
  CHR DMA, DP/DB/stack and queue ownership. Line242 intentionally refuses CHR
  before accepting the smaller final batch; this is distinct from240/241.
- Full four-room route1169–1173: 8,861 frames. Main, renderer, SPC and background
  observer runs match the normal complete PCM and frame/RAM timeline.
- Cadence1176: 3,550 stable loops, all two native ticks, with all consecutive
  stable starts two physical emulator frames apart. Counts by room:598,
  1,746,475,731. Both park directions have no short1/3/4-frame camera holds.
  Longer stops and censored boundaries remain in the report.
- Transport1177: 8,404 packets, 5,613 sweep-write events, all received bytes,
  metadata, key-on rules and completion order pass. Post-final-byte processing
  is458–1,705 SPC clocks. This is not an acoustic-quality measurement.
- Background1178: all871 selected positions match NES pixels, including the
  formerly failing camera266. Coverage259/76/147/389 across rooms0–3.
  The independent strict same-frame publication gate still **fails**, retaining
  961 observations; no waiver. Stable samples are no later than the reference.
- NES replay1179: all37,816 ordered writes executed;15,523 scheduled later at
  their actual packet-publication frame. Three damaged players rejected. No
  original within-frame CPU timing or exact synthesis-fidelity claim.
- CPU producer1175:10,240 executed cases and two damaged variants caught.
  Unchanged SPC driver proof1111 remains available. 801 unit tests and
  `git diff --check` pass.

The complete-route lengths are not an equal-work NES/SNES speed ratio.
Original-speed parity across the whole game is not established.

## Rival trial and restoration

ROM SHA256:
`0956bd97b78f5447619f2e8cf6903e249a3e95b2148cd39f54a6e10151005bba`.
New cartridge `/media/fat/games/SNES/RCR-SNES-0956bd97b78f.sfc` and launcher
`/media/fat/RCR-SNES-0956bd97b78f.mgl` were independently hash-checked.
Observed process PID17795 uses that launcher and SNES_20260603.
The previous071c89e cartridge is preserved and its full hash rechecked.

`tools/capture_mister_boot.py` refuses existing target paths and loads only
after the bounded raw-recorder handshake. Boot recording1183 and combat1209
are each30 seconds. Both owned OBS recordings stopped; raw debug taps were
removed, adapter properties and links restored, and audio routing unchanged.
No speaker unmute, gain adjustment, scene change or saved configuration write.

SNAC was temporarily No for the exact-identity, initially-idle USB pad. The
22.5-second episode is fully inside its recording. SNAC was visually restored
to **Yes** in1215;1218 shows OSD closed and the game paused outside Cross-Town
High School. Saved `SNES.CFG` remained
`066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
No physical SNAC-button test is claimed.

Raw recordings retain original four-channel48kHz signed32 PCM, with FL/FR
sound and zero auxiliary channels. Actual gameplay is non-silent in both
channels. Raw seconds29–29.9 and AAC seconds25–29 are exactly silent while
paused. Dead-gameplay and one-sample paused-click controls are rejected.

Audio audit1216 retains all gaps. AAC gap10.794667s lasts132ms; the corresponding
raw zero span is157.167ms, while video shows Alex knocked down on the street.
AAC gap17.088s lasts129.333ms; raw153.688ms, near pause/resume with the menu
partly visible. Neither is attributed to exact hardware game commands. The
fixed branch offset is266,354 samples, fitted only on seconds4–7. Training
correlation0.955 and held-out0.639–0.787 are weak enough that sample-exact
cross-branch timing is **not** claimed. Both branches share DeckLink/OBS.

Physical-camera1219 accepts all1,792 decoded pairs but detects no scenery
movement in this combat episode: it provides no physical scrolling cadence
qualification. The review retains nine exact decoded hardware frames and six
untouched emulator frames, stream-copy video and native-sample audio clips.

## Next

Reproduce the knockdown-associated silence with actual NES/SNES command-level
evidence, separating intentional sound suppression from lost delivery or
synthesis. Add a hardware episode with real scrolling and retain OBS cadence
limits. Strict publication timing, full-game speed and intermittent pops remain
open. Controller presets and splash sound were not changed in this iteration.
