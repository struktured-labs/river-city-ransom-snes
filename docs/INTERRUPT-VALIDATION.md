# Incremental interrupt checkpoint

Candidate SHA-256: `2098a778f32cadfa886a6dafc59e6f9303342ba9d55d70ed6135bb12402ab4ca`.
Original graphic indices and artwork are unchanged. See [implementation](NATIVE.md)
and the [private collages](audit/README.md).

The same scripted walk, emulator and display frames 1801–3600 give:

| Measurement | Previous publisher | Incremental publisher |
| --- | ---: | ---: |
| Visible picture changes/second | 1.77 | 11.45 |
| Original game-tick changes/second | 13.22 | 11.95 |
| Native NMI counter increments/second | 31.32 | 32.32 |
| Longest NMI gap, display frames | 60 | 74 |
| Black display frames | 71 | 26 |

This is about 6.5× more visible updates, **not** 6.5× faster gameplay or a
full-speed port. Input schedules are identical but game phases diverge, so this
is a workload comparison, not synchronized gameplay benchmarking. Scene-load
stalls and choppy sound remain. The baseline lacked the new VBlank guard.

The new candidate passes 12,000 emulated frames with advancing native NMI
counters and no detected publisher overrun, unknown-I/O fault or SPC timeout.
That establishes liveness, not complete gameplay or audio correctness.

`tools/check_video.py` builds an asset-free cartridge using the production
producer and consumer. It tests two generations, nonadjacent dirty rows, a moved
sprite and a background pattern-table switch against an exact full-frame pixel
oracle. CI also runs the existing native adapter positive/negative controls.
The synthetic cartridge uses native-mode interrupts; the actual game soak
exercises RCR's emulation-mode coroutine adapters. Neither proves real hardware
compatibility.

Reproduce:

```sh
make verify
python3 tools/check_video.py --core /path/to/snes9x_libretro.so
python3 tools/profile_native.py --core /path/to/snes9x_libretro.so \
  --rom build/incremental-final-04/native-cpu.sfc --out build/pacing.json
```

Next timing work: isolate the original game's coroutine waits, bank/PPU hooks
and SPC handshakes. Do not use the higher visible-update rate as evidence that
the original game clock or sound sequencing is now correct.
