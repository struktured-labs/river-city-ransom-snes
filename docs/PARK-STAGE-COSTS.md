# Exact-clock park producer profile · no new Rival deployment

The host-only observer records linked entry points without emulated writes or
added CPU cycles. Its absolute clock includes actual scanline lengths, including
the short NTSC line. It requires a fresh uninterrupted process: reset and
savestate replay are unsupported. Each capture binds its CSV hash, point PCs,
frame window and emulator hash in `capture.json`.

`tools/capture_park_spans.py` resolves PCs from the candidate's linked symbol
files. Four-digit points match replicated runtime banks; six-digit points match
one exact bank, including bank zero. `tools/audit_park_spans.py` verifies the
capture and CSV binding, PC matches, coverage, clock order and frame bounds.
It pairs only adjacent entry points in the same interrupt generation and stable,
unpaused room 3. Reported costs include everything between the two points:
they are not exclusive instruction profiles.

## Production gameplay parent

Candidate: `build/status-pinned-171/native-cpu.sfc`, SHA-256
`0555919b60acd05b25a98973292b29f508aefee3128f88a15ab9bc3a3c55613e`.
This is the unbranded gameplay parent of the current Rival build, including
the Present Status repair. The profile is not a capture of the branded ROM.

Observer: `.deps/snes9x/libretro/rcr_span_ack_libretro.so`, SHA-256
`66426bbce50e6655c2120ea004a11881fb8e6988c292a50cc6b23a02c1a4481f`.

The complete **9,412-frame timeline and WAV are byte-identical** to normal-core
`build/status-park-170`. The isolated single/paired transfer observer equivalence
test also passes: `build/span-observer-equivalence-176/index.html`.

[Detailed stage report](../build/park-spans-audit-176/index.html), raw capture
`build/park-spans-176`, CSV `build/park-spans-176-spans.csv`.
Observation window: raw emulator frames 7535..8105, not the entire park route.

| Adjacent entry points | Samples | Mean master clocks | Maximum |
| --- | ---: | ---: | ---: |
| Deferred camera exit → original NMI return | 263 | 52,930.58 | 112,732 |
| Original sound FA54 → FF29 | 527 | 21,458.57 | 51,308 |
| Audio bridge → video bridge | 527 | 16,444.69 | 18,176 |
| Row preparation → palette | 527 | 11,008.41 | 46,590 |
| Palette → sprites | 527 | 2,663.66 | 2,684 |
| Sprite preparation → CHR tail | 527 | 35,066.99 | 54,058 |

There are **43 NMI-entry intervals over 1.5 nominal frames** in this window.
These are distinct from the **41 late SPC packet-completion intervals** across
the full park replay: different events and different observation windows.

Concrete missed deadline: NMI enters at frame 7618, line 240. Deferred camera
exit is frame 7619 line 100; original NMI return line 161; audio starts line 178;
rows line 191; palette line 214; sprites line 216; CHR tail line 252. The
return polls outside-VBlank for 12,624 observed clocks. Next NMI entry is frame
7620 line 240, about two display frames after the prior entry. This shows a
real interrupt-cadence miss, not merely an unchanged animation image.

The publisher already refuses unblanked late DMA at line 243 or later. Simply
enabling a late NMI is therefore not equivalent to publishing the prepared
frame. Moreover, unconditional return-wait removal was previously rejected;
see [that experiment](NMI-RETURN-WAIT-EXPERIMENT.md). Any selective recovery
needs both interrupt-generation correctness and a safe publication deadline.

## Smaller comparison-loop experiment

`build/park-oam-compare-177` enables only the existing
`experimental_oam_compare_unroll` option relative to the status parent.
It compares eight unchanged words per index update. All other flags and
trace coverage, including the mandatory status repair, remain unchanged.
Default remains off. No game art, original sound engine or overclock changes.

The asset-free native graphics oracle passes, and an executed mutation that
ignores mismatches fails as expected (`tools/check_oam_compare.py`).

[Candidate clock report](../build/park-oam-compare-span-audit-177/index.html),
[full park packet/scene report](../build/park-oam-compare-execution-177/index.html).
The fixed-input replay completes in 9,416 frames. Both games reach the park;
no native faults occur. Late stable-park packets fall from 41 to **14**, but the
worst interval remains **1.7288 frames** (617,830 master clocks), over the
1.5-frame gate. Four extra whole-route frames are not evidence of a global
speedup. Enemy states and timing evolve independently between candidates;
neither the counts nor the mean stage costs establish a matched-state speed
percentage. Do not equate packet cadence with acoustic fidelity.

Candidate observation-window sprite preparation costs: minimum 13,934,
mean 28,813.74, maximum 49,472 clocks, versus parent 20,306 / 35,066.99 /
54,058. These profile distributions are different executions, not paired
identical OAM snapshots. Original sound work can also be costly: its maximum
in this candidate window is 83,098 clocks.

**Not deployed**: the timing gate still fails, and new shop/pause/status
integration captures have not been executed for this candidate. Rival stays
on `RCR-SNES-8bcff69.mgl` (stats repair and improved logo fade).

## Reproduction

```sh
python3 tools/capture_park_spans.py \
  --candidate build/status-pinned-171 \
  --core .deps/snes9x/libretro/rcr_span_ack_libretro.so \
  --out build/park-spans-new
python3 tools/audit_park_spans.py \
  --capture build/park-spans-new --spans build/park-spans-new-spans.csv \
  --normal build/status-park-170 --out build/park-spans-audit-new
python3 -m unittest tests.test_park_spans
```

Six unit tests cover stage pairing, repeated polling, exact bank-zero matching,
wrong-bank rejection, clock resets, incomplete observations, pause exclusions,
interrupt generation changes and malformed/out-of-window rows. Full suite:
316 tests passing after this work.

Next: recover time in the measured original-NMI/sound and graphics paths,
retaining the failed deadline gate. Timing-changing candidates also need
state-aware ordinary-input shop waypoints, rather than assuming old fixed
movement durations still reach the same doorway.
