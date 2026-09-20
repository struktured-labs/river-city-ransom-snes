# Sprite publication deadline: diagnosed, recovered, still offline

Candidate `build/final-batch-slack-trial-3032/native-cpu.sfc`

SHA-256: `a38458515709e0048b5d5b6e5e6ca58888cd3151ea7d839741468f6c106398ba`

[Collages, failed alternatives, native audio and bound proofs](http://127.0.0.1:8766/final-batch-slack-review-3045/)

No MiSTer was accessed. Rivalmage remains occupied/off-limits; Bluemage is
permitted for a future qualified hardware test. This candidate is **not a
release** or a pop-free/full-game speed certificate.

## Actual cause and change

The earlier fixed-picture mismatch is a missed sprite publication, not a new
sprite asset or conversion error. On restored frame 2238, candidate 2990 enters
the final batch at line 249/cycle 1100 and `final_room` at 249/1338. Its beam
latch then sees line 250, so the `CMP #250` guard rejects OAM/CGRAM and the
sprites remain stale. All instructions and the restore-local clock are bound
in traces 3005/3006; their 90-frame controls preserve complete WRAM, registers,
actual pads, pixels and PCM.

Candidate 3032 keeps the exact 2990 interrupt priority composition and changes
only the final-room comparison operand from 250 to 251 (plus ROM checksum).
Row/CHR budgets, preparation, graphics assets, SPC code, and camera policy
remain unchanged. It admits the full final batch at line 250, not beyond.
The ordinary VBlank/upper-beam guards and end-of-publication assertion remain.

Actual replay 3041 now executes the 544-byte OAM DMA at line 250/cycle 1138,
returning on line 254 after 4,522 master clocks. The complete final batch is
also exercised at boundary scanlines in fixture 3037. All 544 physical OAM
bytes are poisoned first, then read back: admitted batches match the staged
buffer; rejected batches preserve the poison. The full batch finishes no
later than line 257 in the 18 recorded cases. The original cutoff is executed
as a negative control and rejects the intended line-250 case.

This fixture covers visible gameplay/non-gameplay branches and selected beam
positions, not every subline phase or transition/palette-preparer state.
These limits remain explicit; more timing margin coverage is appropriate
before deployment.

## Rejected alternatives, preserved

| Trial | Earlier picture gate | Fresh combat | Other result |
| --- | --- | --- | --- |
| 2990 queue priority | FAIL | PASS | Sprite batch skipped at 2238 |
| 3007 check every row scan | PASS | FAIL, two 3-frame intervals | Too disruptive to scheduling |
| 3014 check after row DMA | PASS | FAIL, one 3-frame interval | West sweep has one 1-frame and one 3-frame hold |
| 3032 one-line final slack | PASS | PASS | Both park sweeps have no short irregular holds |

Post-DMA trial 3014 has its own 128-case executed admission/cursor oracle
(3023), including queue ownership, widths, DP/DB/SP, wrap and a rejected
always-continue mutation. It is nevertheless not promoted. Combat failure
2797→2800 has three actual hardware entries before completion (audit 3029).
Renderer correctness passes but pacing does not; neither result is omitted.

Fixture-development failures remain in 3018/3019: endpoint assembler width
was corrected, then the fixture's invalid bank-00 invocation of a low-ROM
helper was removed. Production uses the authenticated C0 FastROM publisher;
the passing fixture verifies this bridge and exercises full-ROM banks C0/40.
The bank-00 claim in the rejected helper's source comment is not supported.
The first final-batch fixture 3036 incorrectly assumed optional dirty latches
were enabled. The authoritative cartridge has unconditional final DMA; 3037
checks real physical OAM and the beam timestamp instead of those latches.

## Current evidence

- Earlier replay 3033: complete byte-rebuilt composition from parent 2769,
  exact initial CPU/WRAM, actual two-pad input. All six original recovery
  gates pass, including unchanged pictures through frame 2240. Later state
  and picture differences are retained, not called equivalent work.
- Newer replay 3042: completion at 2250 instead of 2251, native counts and
  pictures equal through 2252, matching the previous targeted recovery.
- Restore-local trace 3041: bodies and CPU sound packets 1844–1851 each once
  in order, no unserved hardware flag expiry. This is not DSP cadence proof.
- Fresh combat 3034: 4,930 frames complete with neutral observer/two-pad logs;
  strict phases pass, including pause/resume. Busy-inclusive histogram is
  1,753×2 frames with no irregular interval. One scenario, not full-game parity.
- Route 3035/renderer 3038/audit 3043: 9,248 frames, observer neutral, zero
  coverage, split or stale-camera failures. East park: 205×2 + 7×14; west:
  154×2 + 7×14. Encounter stops are retained, not filtered out.
- DSP 3039/audit 3044: full route agrees with normal capture, 8,802 packets,
  1,607 restarts, zero late changed configuration writes, 4,930,267 stereo
  frames, peak 6,559 and no clipping. Exact native DAC/WAV check and a
  late-write trace-mutation control pass. This does **not** establish pop-free sound.
- 1,239 unit tests pass (`/tmp/rcr-tests-3030.log`), and `git diff --check`
  passes. The dedicated boundary/DMA fixtures are separate emulator runs.

Review 3045 verifies 885 source bindings, frame PNG/decoded-RGB integrity,
physical-DMA instruction/clock evidence, failed trials, native WAV copies and
full-route DSP sources. No ROM or save state is published by the review page.

Next: re-run all four fixed NES menu oracles on 3032, broaden the final-batch
boundary cases, and resolve audible sound discontinuity/cadence with waveform
regressions. Only then qualify the improved cartridge on Bluemage.
