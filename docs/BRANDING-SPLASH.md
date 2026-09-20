# Optional Struktured Labs boot splash

This is an opt-in pre-boot animation, **not** a replacement of the game's
artwork, Technos credits, title/menu strings, or gameplay. It does not require
the earlier footer-label experiment. Default native builds are unchanged.

The project owner supplied an SL monogram and a separate font reference.
`build_branding_splash.py` crops/resamples the exact monogram without changing
its proportions and isolates only the white lowercase `struktured labs`
lettering from the second reference. No new logo was generated and no music
tagline, ring, waveform, or busy background was imported.

## Asset tradeoffs

The 1024-square monogram source has a 704-square crop, resampled to 184-square
at (36,8). The wordmark crop is (820,264)-(1780,361), resampled to 224x23 at
(16,204). Minimum RGB channel isolates its white text; values below 40 are
black. Thin glow/texture detail is necessarily reduced at SNES resolution.
The composition is 256x239, with 255 used RGB555 colors and 367 deduplicated
8bpp tiles (23,488 bytes), plus a 2 KiB tilemap and 512-byte palette. The
actual emulator image and source/quantized previews are included in the web
audit; this does not claim an exact identification of the source typeface.

## Window mechanism and clean handoff

The user supplied Infidelity's suggested window reveal. The implementation
uses mode 3 indexed 8bpp BG1, scroll registers zero, window 1 left edge zero,
and `$2123=03` (enabled, inverted), with BG1 enabled in `$212C..$212F`.
There is no color math. Mode 3 and register definitions are corroborated by
the [pvsneslib background declarations](https://github.com/alekmaul/pvsneslib/blob/master/pvsneslib/include/snes/background.h).
The enable/invert bit interpretation is independently explicit in
[Snes9x's PPU implementation](https://github.com/snes9xgit/snes9x/blob/7a8878f1306f65594c30b7d86dee41d972c2e495/ppu.cpp).

The right edge advances by four once per VBlank, covering 64 positions
`00,04,...,FC`, then is explicitly set to `FF` for a full-width hold. The
quiet production option holds for 180 frames (three seconds at 60 Hz). The
opt-in bass ident holds for 240 frames (four seconds). The owner found the
original 60-frame hold too brief; the reveal itself remains unchanged.
`WH0=WH1=0` leaves one visible column, not an empty window; the production
art has a black left margin so it initially looks fully hidden. `FC` excludes
the last three columns; a full-width diagnostic ruler verifies this versus
`FF` rather than relying on the artwork's black right margin.

Infidelity's follow-up supplied by the owner emphasizes that `$2126=00`
places the left boundary at the left edge and `$2127=FF` places the right
boundary at the right edge. An unexpected `$2127=00` while this inverted
window is enabled can hide nearly the entire image. The splash deliberately
uses zero only for the reveal start. At teardown it disables window selection
and main/subscreen window masking **before** resetting either boundary;
zeroing the boundaries alone is not cleanup.

Only the reset's checked first five bytes, unused D1 bank, and checksum change.
The reset trampoline runs in native mode with NMI/DMA/HDMA disabled, draws
the splash under controlled display state, force-blanks, disables its windows,
clears all VRAM/CGRAM and DMA channel 0 configuration, and resumes the
original reset at `C0:8005`. Original boot then initializes the game's own
window and display state. No game execution or SPC upload starts during the
splash. The D1 bank must be entirely `$FF`; occupied banks and repeated patch
application are rejected. WRAM `$1FF0/1` phase/edge observations are temporary
and cleared before handoff, then original boot clears WRAM normally.

## Automated evidence

```sh
python3 tools/check_branding_splash.py --candidate build/pause-cursor-coverage-117 \
  --logo assets/branding/sl-monogram-source.png \
  --wordmark-reference assets/branding/wordmark-reference-source.png \
  --core .deps/snes9x/libretro/snes9x_libretro.so \
  --out build/branding-pause-hold180-audit-125
python3 -m unittest tests.test_branding_splash
```

The checker builds and executes production, ruler, wrong-step, dirty-VRAM,
and dirty-window variants in fresh processes. Every reveal and all 180 hold frames are
compared pixel-exactly at RGB555 against the converted image; no image search,
scaling, alignment optimization, or emulator speed override is used. The
fixed one-row source offset reflects native SNES scanline 1 with VOFS=0.

The ruler variant additionally challenges window cleanup with WH1=0 and a
full-width image: stale enabled masking must fail. Another negative control
omits VRAM clearing; the exposed 64 KiB VRAM snapshot must be entirely zero
at the blank handoff. A wrong increment of two instead of four fails the
pixel/timing sequence. All audio during the splash must be silent. Unit
tests independently decode planar data and test patch boundaries/refusals.

Earlier 60-frame prototype's audited parent SHA:
`af7883ec4103688b637b55e43a07837cbe006adf7ee1f979d1e9381d7809cc95`.
Earlier 60-frame prototype's splash SHA:
`fe9abe56caa85b2a7b869f76d0338ad2eb8dfb1a11590313e74b1c8118f273af`.
Production's 329 post-handoff, NMI-matched menu frames have zero display
differences and zero adapter/SPC faults. **183 full game-RAM hashes differ**
and are retained in the report; all 329 nonstack RAM comparisons match.
At matched NMI200 the difference is confined to `$01F9..$01FB`, with one
capture entering NMI and the other in the idle loop. This is not a full-game
behavioral equivalence claim. The opt-in intro adds boot time and must not be counted as a game-speed
improvement or used to loosen existing speed gates. At that time hardware was
unverified and no Rivalmage deployment had been performed.

Follow-up window verification: `build/branding-window-confirm-01/index.html`
reruns all five variants against parent `build/wram-dma-02` (SHA
`6b06329d03641ad26461c6b07d4d59741f84bad5ebbae57e42a4442766062ad9`).
All six aggregate gates pass, including rejection of deliberately stale
window masking, and the three branding unit tests pass. That older result was
emulator-only, not a gameplay performance/audio certification.

## Three-second silent predecessor (2026-09-16)

The new [browser audit](../build/branding-pause-hold180-audit-125/index.html)
and [machine-readable gates](../build/branding-pause-hold180-audit-125/report.json)
pass all six aggregate conditions on the pause/shop-corrected parent
`67010b850f65e0d64732fc8e8c238e33c071ed6c6337531a4814eb5bdcccabdc`.
They cover the 64-step reveal, exactly 180 full-logo frames, silent intro,
complete VRAM clear, wrong-step/dirty-VRAM/dirty-window controls, and original
no-input menu pixels after handoff. The branded image is
`7dc97ab39020c28a7f87bb418b02f17e67e6d0798795293de75b1d06fca34184`.
Exactly this SHA was verified on Rivalmage; its running MiSTer process identifies
`RCR-SNES-7dc97ab.mgl`. Independent Blackmage OBS/DeckLink program screenshots
show [reveal](../build/branding-pause-hold180-audit-125/hardware-0.png),
[full-logo hold](../build/branding-pause-hold180-audit-125/hardware-2.png), and
[original Technos handoff](../build/branding-pause-hold180-audit-125/hardware-3.png).
The screenshots include OBS scene overlays; the large center video area is
MiSTer output, whereas the small SL monogram at bottom right is an OBS overlay
and is not evidence of ROM branding. Hardware display/boot is now witnessed;
At that point hardware sound, full gameplay, and full-RAM equivalence were
still open gates.

## Four-second SPC bass ident (2026-09-16)

The opt-in `--ident-audio` flag generates an original two-voice SPC700
synthesizer for the pre-boot logo: a 32-sample bass with a brighter 16-sample
octave layer. It keys off both voices, mutes them and returns to the SPC IPL
bootstrap before the existing Memblers NES emulator uploads. This follows the
[SPC700 IPL return procedure](https://github.com/gilligan/snesdev/blob/master/docs/spc700.txt)
and [DSP register/sample format](https://snes.nesdev.org/wiki/S-DSP_registers).
No music, effects, or original game graphics are replaced. The source monogram
and wordmark are still the owner-supplied bitmaps.

The first experimental version `3d288bad...` proved the physical audio path
works: the [hardware WAV audit](../build/branding-ident-full-audit-134/hardware-audio/index.html)
measures all 28 notes in the DeckLink recording, a silent lead-in, tapered
cutoff, and returning game music. The owner could hear the game's Technos
sound but *not* a convincing bass drop, so the mix was judged too subdued;
digital presence is not a subjective pass. A stronger two-voice version is
running on Rivalmage as `RCR-SNES-a501f70.mgl` (SHA
`a501f707d4341e2ebaa1ce392a2a3cb327fd87a2703df06e0dee2d5d4f413f49`).
Its [full emulator collage](../build/branding-ident-growl-audit-139/index.html)
passes all seven aggregate gates, including incorrect window/teardown
negative controls and 28 captured-frequency/fade checks. The
[second hardware audio audit](../build/branding-ident-growl-audit-139/hardware-audio/index.html)
also passes eight gates, measuring 28 notes through MiSTer→DeckLink→OBS.
First-note RMS rose from 483.1 to 906.3 PCM units (about 1.88×), while
five seconds of resumed game audio measured 376.5 versus 376.4, so the ident
mix changed without increasing the game's own output. Both captures decode
the same active OBS file; the sample intervals and ROM hashes are pinned in
their individual reports. The owner heard the louder cue and said it was
still flat and stepped, not a chromatic dubstep slide. Digital amplitude did
not certify sound design. The physical frames extracted from that same OBS
recording now appear in its hardware audit alongside the recorded audio.

## Continuous-glide candidate (emulator only, 2026-09-16)

The owner's feedback led to ROM
`7c32f7ddb8daa2e238ebe1c64b3c4a8660baf2afa3f4d2698319e5c8f735a74a`.
It is staged on Rivalmage as `RCR-SNES-7c32f7d.mgl` but is **not running**;
the current physical recording still contains the earlier stepped version.
The [playable fresh-process emulator collage](../build/branding-ident-glide-audit-144/index.html)
passes eight aggregate gates, with [measured continuous pitch](../build/branding-ident-glide-audit-144/ident-audio/index.html)
and a matched dry-ROM negative control. All 287 Python regressions passed
before the separate park-entrance tests were added.

The same two original BRR voices now key on only once and the SPC updates
pitch once per 60 Hz frame: 311→110 Hz through 18 chromatic landmarks over
144 frames, followed by restrained wobble and a 32-frame taper. Pitch
modulation dirties the higher octave and its direct volume is halved. The
144 ms hardware echo occupies ARAM `$A000..$E7FF`, below IPL; the FIR taps
have absolute sum 90 < 128. DSP mute remains active throughout the reveal.
Echo writes first become safe after over a second, but echo *output* is held
at zero for twelve more frames so unknown power-on ARAM cannot be heard.
At handoff the synth silences echo and returns to IPL before the existing
Memblers driver uploads. The [S-DSP register documentation](https://snes.nesdev.org/wiki/S-DSP_registers)
describes both echo memory sizing and the 240 ms EDL-settling precaution.

The original audio-harness gate caught a 101-PCM reveal transient; holding
DSP mute until the first actual note eliminated it. All twelve measured
glide windows pass; a matched dry build has **zero** PCM difference in the
first eight note frames and then differs by 471.61 RMS PCM (22.61% of wet)
after echo warms up. The original menu is pixel-identical at 384 matched
frames with zero non-stack game-RAM difference. These are digital tests; the
owner still needs to listen to the new cue on real hardware.

`tools/audit_ident_hardware.py` now expects this legato curve (twelve audio
checkpoints); its existing 28-note reports are historical evidence generated
by the prior version of that checker. When the new build is launched, a
repeatable physical test requires a new live MiSTer→DeckLink recording and
contemporaneous OBS input-mute settings. Do not attach the old recording to
the new ROM or imply that game SFX and overall performance are certified.

## Hardware feedback and longer fade (September 16, 21:47 EDT)

The continuous-glide ROM `7c32f7d…` was booted on Rival at 21:42:37 EDT.
The physical OBS capture passed all twelve frequency checkpoints, but its
final half-second retained 55.18% of the initial half-second RMS, failing the
existing 50% taper limit. This was a fade-envelope failure, not a detected pop:
the maximum adjacent PCM step was only 325 at 16 kHz.

The fade is now **48 frames / 0.8 seconds**, instead of 32 frames. All eight
emulator splash/audio aggregate gates pass in
[branding-ident-fade-audit-163](../build/branding-ident-fade-audit-163/index.html).
Original gameplay parent remains `67010b850f65e0d64732fc8e8c238e33c071ed6c6337531a4814eb5bdcccabdc`;
the experimental sprite-speed changes are **not** included.

Rival was restarted at **21:47:35 EDT** using `/media/fat/RCR-SNES-ad2060f.mgl`.
The deployed ROM was SHA-256 verified after copying:
`ad2060f5e29741fd331debc7ae5f61562c6f08acde05fa31bfd1a3306b22a02f`.

[Physical audio, screenshots and eight-gate audit](../build/ident-fade-hardware-164/audit-final/index.html)
come from seconds **110–140** of Blackmage's already-active OBS recording
`20260916_214537_struktured_v6c_part2.mkv`. The ident starts at **121.12 s**.
All eight checks pass: twelve glide frequencies (maximum error **1.323%**),
audible bass/taper, silence before and after, return of original game audio,
and no overload/splice transient above the stated thresholds. Tail RMS is now
**35.99%** of the initial half-second; maximum adjacent step is **323** PCM.
These measurements do not establish subjective dubstep timbre or absence of
all audible flaws. They do establish physical output, not merely emulator sound.

The OBS settings were read immediately before this reboot and again afterward:
RCR scene, active recording, live/unmuted Blackmagic, desktop and mic muted.
The read-only helper `tools/read_obs_audio_provenance.py` records an explicit
observation timestamp and does not claim historical settings outside that time.
It uses local `websocket-client`, an SSH localhost tunnel to OBS port 4455,
and the existing remote credential without writing it into receipts.
OBS recording, scene selection, replay state and mute settings were not changed
by the agent. The user changed recordings between the two hardware tests, and
each extraction is bound to the actual corresponding file.
