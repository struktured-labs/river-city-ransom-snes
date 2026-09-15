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

## Interrupt-mask diagnosis, 2026-09-15

Local mono-routing candidate `d058e05d038513bbb703c20d82b75525a878e12821d0187fb610328dc06c7f36`
was run for 3,600 display frames with the `walk` input profile. The instrumented
core SHA was `e62e8d9e636db679be95f19262d582cca41abc83a46ac27ddac92e53be004bf2`.
Its PCM hash matches the prior stage-instrumented execution:
`cb76fb9a236c03c7c0071ea5fc433c815aae6a3d0c4027cda067c0cd654a41c9`.
The transition trace starts at emulator frame 1800; it is local ignored evidence
at `build/mono-audio-01/enables.csv`, SHA
`388383a357b16e610a939240760722a62973ef1f675b4ab4826b9e55f474bc5f`.

Across completed interrupt-masked intervals, 757 line-240 VBlank edges were
masked. Of these, 568 fall in intervals opened by `bank_switch_enter` (trace PC
Cx:2354, immediately after its STZ $4200); 124 fall in intervals opened by the
NMI handler itself, and 65 in other adapter paths. These are mask-edge counts,
not an independent original-game-speed or audio-fidelity oracle.

Example: the bank switch at frame 2134, line 238, cycle 1082 disables NMI.
It re-enables at line 0, after the VBlank edge has passed. The exit adapter
explicitly waits outside VBlank. Similar bank-switch intervals mask the next
two edges; the next recorded NMI entry is frame 2137, line 240. Stage tracing
also shows a roughly 62-line clean graphics preparation cost, with longer
preparation when dirty rows are converted, sometimes repeated by PPUMASK.

The paired-bank guard must remain: removing it previously allowed sound NMIs
to corrupt an unfinished R6/R7 switch. The next implementation experiment is
safe late-NMI delivery **after** the pair is complete. This also requires a
late-entry graphics budget check: the final OAM/CGRAM batch is currently
unconditional, so merely deleting the VBlank wait is unsafe. Coroutine stack
shape, no duplicate delivery, full settings pixels, long walking progression,
and audio cadence still need regression coverage before hardware deployment.

The tracked SNES9x debug patch now exposes `RCR_ENABLE_TRACE`. CSV columns are
frame, beam line, cycle, PC after the write, NMITIMEN value, task, NMI depth,
bank guard, and shadow PPUCTRL. It records changed writes after frame 1800.
`tools/analyze_nmi_mask.py` assumes NTSC non-interlaced line-240 NMI and handles
the core's frame counter advancing at line 1 rather than line 0. It ignores
an incomplete final interval and reports that limitation. Five unit tests
cover normal entry, an edge crossing, line-zero wrap, multi-frame masking,
and out-of-order evidence rejection.

```sh
RCR_ENABLE_TRACE=build/enables.csv python3 tools/smoke_libretro.py \
  --core /path/to/instrumented/snes9x_libretro.so \
  --rom build/mono-audio-01/native-cpu.sfc --kind native --profile walk --frames 3600
python3 tools/analyze_nmi_mask.py build/enables.csv --out build/masked-edges.json
python3 -m unittest discover -s tests
```

All 46 unit tests pass at this checkpoint. No new runtime change or Rivalmage
deployment is claimed by this diagnostic work.

### Late bank-exit delivery experiment

Candidate `build/late-bank-03/native-cpu.sfc`, SHA
`754bbf0d37bc3f5c5a965ce5f42a64dc7326ff06ab2faf51121787754e275a33`,
removes only the bank-exit wait-outside-VBlank loop. The atomic pair/depth
guards remain. NMI entry already acknowledges $4210; bank exit can therefore
deliver a still-pending edge after completing the pair. The publisher now
rejects late entry, reserves another scanline for row DMA, and checks the
remaining budget again before its final OAM/CGRAM batch. Early experiments
without that final check failed the overrun oracle and are not candidates.

The 12,000-frame walk has no detected VBlank overrun, adapter fault, or SPC
timeout. Over frames 1801–12000 it measures 53.99 NMIs/second, 16.18 picture
changes/second, and 13.81 sampled game-counter changes/second. The preceding
block-OAM baseline measured 37.27, 13.51, and 17.30 respectively. Thus this
recovers interrupt delivery but **does not demonstrate faster gameplay**;
the game-counter metric actually decreases. Different scene occupancy also
prevents treating these whole-run metrics as matched game simulation speed.

The phase audit in `build/late-bank-quality-03/site/index.html` has verified
bundle integrity, passes its settings pixel and basic audio activity gates,
but still fails all four transition timing gates. Native capture takes 2672
frames versus the NES reference's 1936 (the previous mono candidate took
2425). More frequent interrupt work leaves less main-thread time; reducing
producer/adapter overhead is the next target. Basic audio activity does not
establish musical timing, absence of sputtering, or sound-effect fidelity.

The asset-free graphics harness includes a deliberately delayed first NMI at
line 260: staged rows must remain queued and subsequent normal interrupts must
produce the exact expected image. Removing both late-budget guards must fail
the executed assertion. The test checks both frame-counter bytes so it does
not accidentally repeat at counter 256. This candidate is local experimental
work, not a deployment or a full-speed release.

### Cached preparation follow-up

`build/cached-producer-01/native-cpu.sfc`, SHA
`9b891eed491664e393510eb7b6293947cdad3caad67973f83e252470856b19a1`,
compares actual palette and OAM shadow bytes before reconverting them. Palette
snapshot storage is $7E5580–559F; OAM snapshot storage is $7E5600–56FF. The
sprite pattern-table bit is cached separately at $1C86. The existing first-
publication flag forces initialization even when zero-filled source and cache
match. Unused SNES sprites/high OAM are initialized once. All comparisons and
publication snapshots remain inside the NMI-masked producer bridge.

The same 12,000-frame workload measures 55.16 NMIs/second, 19.09 picture
changes/second, and 15.93 game-counter changes/second, with no detected VBlank
overrun or adapter/SPC fault. This improves on late-bank-03, but still does not
establish original-speed gameplay. Street-scroll samples reach 440 rather than
511 in this run; neither range proves traversal or identifies a scroll failure
without a phase-matched positional oracle.

The audit at `build/cached-quality-01/site/index.html` verifies bundle integrity
and passes its settings pixels/basic audio activity gates, but all four timing
gates still fail. Its SNES capture is 2642 frames versus NES 1936. The full
audio-fidelity and physical-hardware release requirements remain unverified.

The graphics test now changes palette bytes and toggles the sprite pattern bit
while OAM is unchanged, checking staging contents before restoring the final
pixel oracle. Mutants that ignore either change must fail executed assertion
7. Normal, scrolling, late-entry, lost-row, disabled-HDMA, and cache-invalidation
checks pass; 46 unit tests pass. No Rivalmage deployment was performed.
