# Quality benchmark — failing baseline, not a new playable build

The user's release bar is original NES speed and no sputtering or dead sound.
The current candidate does not meet it. This harness is designed to expose that,
not to rename emulator liveness as game correctness.

## September 15 local progress (not deployed)

### Timing-sensitive failure reproduction

Follow-up: the bank switch at `$FED1` is now protected across both MMC3 PRG
register writes. Ordinary I/O stubs keep NMI masked while `$1C83` is nonzero;
the `$FEFB` exit validates the selected bank and then restores NMI eligibility.
The replaced instructions preserve the original stack layout. A failed bank
check reports an adapter fault instead of executing the NES `$80` NOP as a
65816 relative branch. This does not implement the missing raster IRQ.

With this fix, `build/atomic-bank-fast-01` (SHA-256
`11c97e0d11b636e8f98c7e400c58c9499efc580954adfe0e9fd5f97bf97969e4`)
reaches all baseline phases in 2,510 frames. Its settings pixel check passes;
idle and attack audio-presence checks pass. Four transition gates, walk/resume
audio, and pause-tail noise still fail. Dashboard: `build/atomic-bank-quality-01/site`.
The faster option remains opt-in. Below is the preserved **pre-fix** reproduction.

`tools/build_native.py --experimental-fastrom` now preserves a diagnostic
experiment; it is **off by default**, not a speed fix. With the title-05,
walk-02 and inventory-02 traces it generates SHA-256
`f91c70ee810215aa30489bdbb8271167302670ce3ebaef1556cb4d8b087f8147`.
It selects hardware MEMSEL fast ROM timing and the matching HiROM header.
The unchanged default still generates the jump-button candidate byte-for-byte.

`build/fastrom-quality-01/site` records the failure: boot recognition takes 366
frames, then NMI progress stops at counter 139 **before the scheduled Start
press**, during the menu idle period. CPU ends at `$00:2020`; task/guard bytes
change unexpectedly. Settings recognition subsequently times out at 2,400 frames.
This is not yet proof of the same freeze seen on Rivalmage.

The trace in `build/fastrom-repro-02/cpu-trace.txt` ends with the normal menu NMI
return at counter `$008B`, entered with a deeper stack than prior interrupts.
Next investigation is interrupt entry/return during bank-switch helper execution.
Do not assume faster ROM is safe until this corruption is understood.
A 600-frame coarse smoke run misleadingly passes (counter advanced between its
two sample points); the 900-frame run correctly fails `Native NMI counter stalled
or reset`. The phase benchmark also rejects the run. Short liveness runs cannot
certify this failure away.

Dedicated jump mapping: SNES **A** now supplies both NES action bits, equivalent
to the existing **Y+B** chord, for either player. Y and B retain their individual
actions. The production serial adapter latches the first nine SNES button bits
on the strobe's falling edge and exposes the mapped eight-bit NES controller.
`tools/check_adapter.py` executes A-vs-Y+B tests on both ports, plus an absent-input
negative control and the existing Select/Start tests. This is input equivalence,
not yet physical SNAC or animation-level jump certification. X is unchanged.

Candidate `406482a448c128987266b1a37a67d10781bc7aaf64d678ee1801cf7551fdb8f3`
is in `build/gameplay-audio-01`; its verified audio/collage dashboard is
`build/audio-quality-01/site/index.html`. Historical evidence below is preserved.

Two concrete defects were addressed:

- Prepared tile rows were being revoked by subsequent NES shadow writes. Row
  flags now encode dirty and ready independently: 0 clean, 1 dirty, 2 ready,
  3 ready plus newer dirty data. The consumer drains the immutable staged row,
  retaining the new dirty bit for the producer. The asset-free executed graphics
  test passes; a disposable mutation restoring the old consumer fails. Settings
  heads disappear and NORMAL/FAST return, but the footer still fails comparison.
  A build without the added inventory trace has the same settings screenshot,
  isolating that improvement from expanded code coverage.
- Gameplay calls the sound driver at `$FA54` from its first MMC3 IRQ (`$F1D9`
  entry), whereas menus call it from NMI. The port's disabled raster IRQ left the
  street music initialized but never advanced. A temporary NMI-return service
  calls that driver for gameplay tasks only, preserving bank variables as the
  original IRQ does. **This is not accurate raster timing or a complete IRQ port.**

Idle audio activity rose from 0% to 91.7%; walk/resume reach 81.1%, attack 96.7%.
Idle/walk/resume still have 4–5-frame silent runs. The attack presence check passes,
but fidelity is unverified and pause-tail noise fails. Transition waits remain
409/141/136/758 frames versus NES 170/53/54/459. Nine automatic gates still fail.

The 12,000-frame smoke run passes NMI-progress and adapter-fault checks only;
it does not establish gameplay speed or audio correctness. The 2,836-frame
Start→confirm submenu run reaches every scheduled phase without an adapter fault.
The reported physical blue-screen freeze has **not** been reproduced or resolved.
Rivalmage was not accessed or changed for this work.

`benchmark_capture.py --scenario start|select|start-select|start-confirm` adds
bounded street/menu input scenarios. New captures include CPU/task/PPU/APU packet
telemetry and phase-end RAM snapshots, bound to their receipt and final-frame RAM
hash. Old captures remain verifiable. The full quality report rejects diagnostic
scenarios instead of mislabeling them as the baseline release benchmark.

Next: implement proper interrupt scheduling and measure game/audio cadence;
remove the provisional service when the real first-raster-IRQ path is in place.
Keep the blue-screen reproduction, remaining settings pixels, audio dropouts and
pause behavior open. No playable handoff until the original-speed/audio bar passes.

## Reproduce

```sh
python3 tools/bootstrap_nes_core.py
python3 tools/benchmark.py \
  --snes-core /tmp/rcr-snes9x/libretro/snes9x_libretro.so \
  --candidate build/incremental-final-04 --out build/quality-run
```

Use a fresh output directory. The command exits **1** for failed or incomplete
quality gates and still generates `site/index.html`. Core/callback errors abort
capture rather than fabricate later phases. The NES source ROM and authenticated
reference captures stay local. `tools/bootstrap_core.py` can reproduce the SNES
core instead of using the existing `/tmp` build.

```sh
python3 tools/verify_benchmark.py build/quality-run/site
python3 -m http.server 8766 --bind 127.0.0.1 --directory build/quality-run/site
```

Open the loopback dashboard for phase-seekable NES/SNES audio, AC-amplitude plots,
screenshots/differences and evidence-bound review notes/export. Audio playback is
never automatic. The opposite player pauses when a phase button is clicked.
The checked-in GitHub summary deliberately omits recorded game audio and ROMs.

## What is measured

Both systems execute the original logical input sequence, in separate emulator
processes, with the same external NES palette. Small white-glyph templates detect
menu, settings, completed story text and street. Each transition requires three
consecutive matching frames. Recognizing a heading does **not** certify that the
entire screen has finished drawing; full-screen comparisons remain separate.

The sequence includes settling periods, idle, walking, pulsed attacks, a Start
pause request and resume. Transition waits are bounded; an unreached screen stops
the sequence. No save-state shortcuts, game RAM writes or frame skipping occur.
Phase-driven actions permit meaningful input comparisons despite slow startup;
the images are explicitly **not cycle/frame-synchronized**. Enemy/RNG state can
diverge. Different total run lengths are intentional evidence of slow transitions.

Every frame records requested and returned controller buttons, audio sample count,
AC RMS/peak, contiguous PCM offsets, framebuffer hash, original-RAM hash and
adapter faults. `$052B` is recorded as an unvalidated probe, not labeled game FPS.
The original ROM, candidate manifest, cores, capture tool, scenario, reference
images and palette are hash-bound. The verifier recomputes audio metrics from
PCM, checks phase/frame/input continuity and checks screenshots against telemetry.
Hash binding detects accidental changes; it is not a signature against someone
who maliciously rewrites the entire evidence bundle and its hashes.

Current automatic gates:

- Transition time: at most original duration plus max(2 frames, 5%). This limited
  transition test is not the unfinished full-gameplay-speed certification.
- Active gameplay audio: when the NES phase is active ≥95% of frames, the port
  must be active ≥90%, with no silent run longer than three frames. “Active” is
  AC RMS >8 in int16 units, measured per channel before combining power. DC does
  not count as sound, and out-of-phase stereo does not cancel to false silence.
- PCM callback continuity (one partial startup frame is explicitly allowed).
- Full settings-screen RGB555 comparison against the authenticated NES capture;
  no masking out the reported heads or missing text. Blink differences are visible.
- Pause-tail noise: conditional on audible candidate gameplay first. A completely
  dead engine cannot earn a pause/silence pass. A Start request alone is not proof
  of pause state; its video and audio effects remain visible to the reviewer.
- Requested input delivery and native adapter/VBlank fault checks.

Full-game speed, music/SFX fidelity and physical hardware audio remain explicitly
**unverified** and block release, even if every implemented check eventually passes.
Amplitude/activity gates cannot catch every kind of wrong timbre, retriggering,
pitch or sputtering. Human listening is required alongside future event-level
APU and game-state oracles. The dashboard never turns saved notes into a release pass.

## First reproducible result

Candidate `2098a778f32cadfa886a6dafc59e6f9303342ba9d55d70ed6135bb12402ab4ca`
(the same build tested on Rivalmage; no new ROM deployed).

| Transition wait | Original NES frames | SNES frames |
| --- | ---: | ---: |
| Boot to menu | 170 | 455 |
| Settings | 53 | 158 |
| Completed story text | 54 | 160 |
| Street | 459 | 749 |

Idle, walking, attacks and resumed gameplay have audio on every measured NES
frame but **zero active audio frames on SNES**. Settings reproduce leftover heads
and missing message-speed text. This is nine failing gates, not a near-release.
The paused tail is quiet on both in this run; paused sputtering is not reproduced
and cannot be marked fixed while gameplay sound is dead.

Two independent full runs produced identical per-frame telemetry and PCM hashes
for each system. NES: 1,936 frames; SNES: 2,722 frames.

| Evidence | SHA-256 |
| --- | --- |
| NES timeline | `35412acd2ef0c977152336bad1c10b53bc79375a42555bd4e26ace6281cae31f` |
| SNES timeline | `d3117ad8e20b49fa8624b2c18ed3987a966150b783a3907456aedc8c18b48504` |
| NES WAV | `40da6a3c1531bfc983ecfca476bd199958f8301385ce53682eefa88db10d31d1` |
| SNES WAV | `80fe50ee2061aa9cf8d8b8d2ca00b0fa744449eea7399519b069ad3220eb74b7` |

## Harness tests and Select

`make verify` includes negative tests for silence, DC, short dropouts, wrong
pixel formats/padding, empty classifiers, altered images/audio/HTML, rehashed
wrong metrics/input, skipped frames/phases, false completion and release claims.
`tools/check_benchmark_ui.mjs` executes the generated JavaScript to test audio
seeking/mutual pause and review save/reload/export/new-hash reset. This is a DOM
contract test, not a browser layout or actual speaker playback test.

CI runs the asset-free tests and verifies the checked-in **failing** evidence.
A green CI run means the harness and controls passed, not that this commercial
game passed its quality benchmark. The full original-ROM benchmark runs locally.

The asset-free native adapter cartridge now additionally exercises **P1 Select
and P2 Start**, reads all eight serial bits on both ports, and checks that other
buttons/ports do not leak. Omitting the inputs fails the exact CPU-side assertion.
This verifies the production input bridge in Snes9x, not physical SNAC wiring or
the meaning of Select on every RCR screen. Rivalmage's SNAC has been enabled and
the user confirmed controls there. No further Rivalmage interaction is needed.
