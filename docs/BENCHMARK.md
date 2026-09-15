# Quality benchmark — failing baseline, not a new playable build

The user's release bar is original NES speed and no sputtering or dead sound.
The current candidate does not meet it. This harness is designed to expose that,
not to rename emulator liveness as game correctness.

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
