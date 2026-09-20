# Park PPU-ring costs and interrupt guard · not deployed

## Exact missed-frame instruction profile

The previous [field-pair sprite experiment](SPRITE-PAIR-EXPERIMENT.md) made
sprite conversion substantially cheaper but still missed packet deadlines.
`tools/snes9x_instruction_trace.inc` adds host-only instruction-entry clocks,
PC/opcode and registers. Rows are flushed and the capture receipt binds the
trace hash and observation bounds. No emulated memory write or extra cycle is
introduced. Elapsed time between entries includes DMA and event handling; it
is not an exclusive per-instruction CPU-cycle measurement.

Observer `.deps/snes9x/libretro/rcr_instruction_ack_libretro.so` SHA-256:
`31075da0f9f8acecd9474a2e1d082d254df71f5470c4adaf5b8fb5582b75dde5`.

Capture `build/park-instructions-184`, frames 7803..7805, records 48,691
instruction entries. Its entire 9,412-frame timeline and WAV are byte-identical
to `build/park-sprite-pair-spans-178`. The ROM is the field-pair candidate
`7406182e4db1fa9081fe6dbc9895a7f69cafae01b809c59cadc61907d49ba943`.

[Instruction and original-call-site report](../build/park-instruction-audit-184/index.html).
`tools/audit_park_instructions.py` verifies both trace bindings, exact stage
boundaries and control equality before attribution. Raw frame 7804:

| Original NMI call | Elapsed master clocks |
| --- | ---: |
| FDF4 from F16D | 15,114 |
| FC4D from F18C, PPU update | 64,828 |
| E6BF from F19E | 386 |
| E30A from F1A1 | 360 |
| E2D2 from F1AC | 4,094 |
| FF07 from F1D0 | 7,106 |

Complete camera-exit → original NMI-return interval: 102,094 clocks.
Original sound FA54 → FF29: 49,066 clocks. Sprite preparation in the same
missed frame: 15,716 clocks. The next optimization target is therefore not
another broad sprite-conversion rewrite. Original call sites were checked
against disassembly of the supplied NES ROM, not inferred from symbol names.

## Isolating the existing PPU-ring experiments

All candidates below retain the field-pair converter and Present Status repair.
The input script and 1.5-frame stable-park packet deadline are unchanged.

| Variant | Build | Late packets | Worst interval (nominal frames) |
| --- | --- | ---: | ---: |
| Field-pair parent | 178 | 12 | 1.7065 |
| Native ring consumer | 185 | 17 | 1.6551 |
| Cached ring address | 186 | 15 | 1.6919 |
| Both, **missing interrupt guard** | 187 | 0 | none over threshold |
| Both, **guard corrected** | 192 | 6 | 2.0126 |

Reports: [consumer](../build/park-ring-execution-185/index.html),
[address cache](../build/park-pointer-execution-186/index.html),
[unsafe combined](../build/park-ring-pointer-execution-187/index.html),
[corrected combined](../build/park-ring-pointer-guard-execution-192/index.html).

The zero-gap result was real for that execution but **superseded**, not a
deployment qualification. Enemy states, room exposure and event timing differ
under identical inputs. These counts are not a percentage speedup or proof
of original NES speed. No new hardware/acoustic-fidelity claim is made.

## Corrected interrupt ownership

Inspection found that `native_ring_consumer` unconditionally re-enabled NMI
at return, unlike the existing translated PPU adapter. It now checks both
`$1C0A` (NMI depth) and `$1C83` (bank-pair critical-section depth). If either
is nonzero, the owning caller retains responsibility for re-enabling NMI.
The ordinary unguarded return still enables it according to PPUCTRL; return
flags and A=0 semantics are retained.

This does not affect the current live gameplay build: the native ring consumer
is opt-in and remains disabled in that build.

[Executed combined ring/address-cache oracle](../build/ring-consumer-guard-oracle-193/report.json).
Existing command budgets, ring wrap, buffered reads and ABI checks pass. New
tests observe **real subsequent VBlank interrupts**, rather than attempting to
read write-only NMITIMEN:

- Case 37: NMI-depth guard suppresses an interrupt.
- Case 38: bank-pair guard suppresses an interrupt.
- Case 39: unguarded return permits exactly one interrupt.

Independent mutations removing the NMI guard and ignoring bank depth fail
cases 37 and 38, respectively. Missing read-pointer updates still fail case 32.
Mutant ROM hashes, logs and positive receipt binding are retained in the report.

The fixture needed its own bank restoration after the positive interrupt:
emulation-mode RTI does not restore PB. The minimal fixture handler returns to
bank zero's identical high-ROM test code; a synthesized RTL restores the saved
test bank before subsequent low-address runtime calls. Without this fixture
repair, the positive test caused a later unrelated case-24 failure. The
production port already has a bank-aware return path; it was not replaced.

Corrected candidate `build/ring-pointer-guard-native-192/native-cpu.sfc` SHA-256:
`5ac817a86c27c657d0dac9bf3d09677ea87057cee597c2184647e62f3abfccc5`.
Its 9,407-frame park replay has no native faults and reaches room 3. Six late
packet intervals remain; the worst is 719,232 clocks at frames 7761..7763.
The narrower profile window has four late NMI-entry intervals. **Timing FAIL**.

## Integration and traversal problem

The pre-guard combined candidate's fresh status capture passes original pixels
and RAM values ([report](../build/ring-pointer-status-audit-188/index.html)).
Its pause cursor test still fails only the closing checkpoint with 718 differing
pixels ([report](../build/ring-pointer-pause-audit-188/index.html)). These results
are for ROM 187, not automatically transferable to the guarded ROM 192.

Both shop checks fail, and screenshots show why: the ordinary fixed-duration
script is **outside the café**, not testing a broken YES/NO menu. With ROM 192,
`observe_alley_exit` still reports room 1; the later `enter_shop` input actually
enters mall room 2. The old field-pair route had already reached room 2 at the
alley-exit checkpoint and then entered the café normally.

Failed checks are retained, not relaxed:
[repeat purchases](../build/ring-pointer-shop-repeat-audit-188/index.html),
[YES/NO](../build/ring-pointer-shop-no-audit-188/index.html).
Next: add state-aware ordinary-input traversal checkpoints before claiming
shop-menu regression coverage for timing-changing candidates. Also retain
the six missed deadlines and pause-close timing discrepancy as open work.

No Rival restart or deployment in this experiment. Live remains
`RCR-SNES-8bcff69.mgl`. Full Python suite: 321 tests passing; complete adapter
positive/negative controls and the new combined ring oracle pass.

## Reproduction

```sh
RCR_INSTRUCTION_TRACE=build/park-instructions-new.csv \
  python3 tools/capture_park_spans.py --candidate build/sprite-pair-native-178 \
  --core .deps/snes9x/libretro/rcr_instruction_ack_libretro.so \
  --out build/park-instructions-new --first 7803 --last 7805
python3 tools/audit_park_instructions.py --capture build/park-instructions-new \
  --control build/park-sprite-pair-spans-178 --trace build/park-instructions-new.csv \
  --spans build/park-instructions-new-spans.csv --frame 7804 \
  --out build/park-instruction-audit-new
python3 tools/check_native_ring_consumer.py \
  --core .deps/snes9x/libretro/snes9x_libretro.so \
  --out build/ring-consumer-guard-oracle-new --pointer-cache
```
