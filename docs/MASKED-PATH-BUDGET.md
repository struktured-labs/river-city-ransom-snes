# Complete masked-path budget: two causal recoveries, still offline

Candidate `build/masked-budget-trial-2696/native-cpu.sfc`, SHA256
`825c35c3732b84d32cb0629728b3a66d18b68843c8832f1e8313e545c8d34e52`,
extends retained-producer guard2673. It is not deployed. Rival remains on
harmonic splash2648; no hardware/OBS/controller changes occurred this turn.

[Two exact-state collages, native audio, all failures](http://127.0.0.1:8766/masked-budget-review-2705/)
· [Full-route renderer](http://127.0.0.1:8766/masked-budget-render-audit-2706/)

## Change and rationale

The previous producer cutoff accounted for only the graphics pass. Actual
neutral instruction trace2694 takes157,434 and177,672 master clocks from
camera-guard entry to complete retained return:115.42 and130.26 nominal
scanlines. That includes the original game interrupt and following producer.

This trial changes both camera and retained-fallback admission from194 to120.
Line120 leaves142 lines until the end of overscan VBlank, roughly11 beyond the
longer observed path. This is an empirical experiment, **not a universal
worst-case bound**. Only16 immediate bytes (two per mirrored runtime bank) and
cartridge checksum change. Graphics, audio code/data, game timers and pending
ownership machinery remain unchanged. Parent194-line helper provenance remains
explicit in the new manifest rather than borrowing its qualification.

## Same-state proof

Checkpoint2695 captures2716 and2723 without changing the entire4,929-frame
normal run, PCM or actual two-port callbacks. Fresh-process controls2697/2698
each reproduce90 frames exactly. Trials2699/2700 require identical initial
128KiB WRAM, all CPU registers, recorded physical inputs, and an exact newly
reconstructed16-immediate patch. Historical instruction counters are not
enabled during saved-state replays.

| Known failing state | Previous completed update | Trial completed update |
| --- | ---: | ---: |
| Frame2716 checkpoint | 2720 | 2719 |
| Frame2723 checkpoint | 2727 | 2726 |

Each trial recovers the missing native NMI count and original completion
increment. First four/five pictures respectively remain identical; later
execution diverges. Cross-ROM equality is intentionally false, while valid
same-state comparison is true. Full90-frame differences remain in each receipt.
Initial/final scheduled-minus-served counters equal pending ownership modulo
65536. The first trial ends with one pending job, not silently asserted drained.
Endpoint conservation does not prove continuous queue deadlines.

## Regression evidence and limitations

- Oracle2703 executes the actual camera and retained guard bytes in129 beam,
  pending/ordinary, mirrored-bank and wrapped-stack cases. It verifies
  X/Y/SP/DP/DB and the saved interrupt frame. All three binary old-cutoff
  controls fail the new admission decision. Downstream routines are dispatch
  spies; this fixture is not a full graphics/NMI timing proof.
- Two-player campaign2701 has same-core normal/observer full timeline/PCM and
  actual port equality. Sustained attacks has1,753 stable two-frame intervals
  and no three-frame intervals. Running/jumping has1,743 two-frame and three
  three-frame intervals:2237–2240,2250–2253,4315–4318. Strict running combat
  still fails. Changed encounters preclude a matched-work speed ratio.
- Full-route renderer2704 is neutral against2702 over8,874 frames. Audit2706
  checks7,266 eligible complete frames and6,304 held-camera observations,
  with zero missing coverage, splits or stale camera. No full tile/menu or
  physical-scrolling correctness claim follows from this scoped result.
- DSP2712/control2711 are neutral. Audio audit2713 compares against2673,
  verifies8,432 packets and1,548 voice restarts, with no late changed setup
  writes. Raw DAC matches4,730,880 native stereo samples, peak6,339, no clipping.
  Its late-write negative control is rejected. Waveform fidelity, perceptual
  pops and physical audio are not certified by transport/order tests.
- Full suite:1,181 tests pass (`/tmp/rcr-tests-2708.log`). Added tests check
  exact patch scope, mirrored preimages, duplicate/repeated patch rejection,
  and ownership accounting including wrap. Review2705's119 sources and29
  artifacts verify; its browser collage was visually inspected.

## Why an earlier graphics cutoff is not the complete fix

Fresh instruction control2707 and two observed windows2709/2710 are neutral
over all4,929 frames and PCM. Their remaining failures bypass the graphics
producer correctly, but the original retained game interrupt itself crosses
the entire VBlank:

| Case | Camera guard | Original game NMI starts | Original body ends | Interrupts re-enabled |
| --- | --- | --- | --- | --- |
| 2237–2240 | 2238:228 | 2238:229 | 2239:21 | 2239:79 |
| 4315–4318 | 4316:238 | 4316:239 | 4317:4 | 4317:29 |

At the next early scanline, the beam-only guard considers the wrapped frame
early and services pending graphics. The edge was already lost inside the
original body; skipping that later graphics work alone cannot recover it.
The first original body takes73,678 clocks. Instruction-cost inspection points
to translated PPU command copying and adapter work as substantial costs, not
only native graphics preparation. Optimizing those exact routines with
data/ABI oracles, or designing a correctly queued interrupt service, is the
next meaningful direction. Merely lowering the cutoff again cannot solve
an original body entered at line239. The three-NMI2250–2253 interval also
remains unclassified against matched NES work.

Keep this candidate offline pending those fixes, menu/status regression,
one-player cadence, and actual Rival scrolling/audio validation. The full
speed/scrolling/audio goal remains open; no gate was relaxed.
