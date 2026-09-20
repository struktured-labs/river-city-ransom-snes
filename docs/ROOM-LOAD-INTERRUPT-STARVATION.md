# Room-load interrupt starvation — measured, unresolved

Rival remains on `765052c`; none of these experiments were deployed.

## Timing gates now include the whole load

`audit_room_entry.py` additionally anchors on the observed room-change and
rendering-off edges, retaining the original rendering-enable-relative pixel
comparison. Missing edges, discontinuous frames and missing visibility fail.
A negative unit test explicitly rejects moving work before rendering-enable
to manufacture a speed improvement.

| Capture | Frames from room change to first scenery, rooms 1/2/3 |
| --- | --- |
| Original NES | 20 / 31 / 30 |
| Live branded ROM | 45 / 51 / 52 |
| Twelve-row + native alias words | 27 / 34 / 33 |
| Above + 4096-byte hidden DMA | 28 / 33 / 33 |
| Above + full hidden row-ring scan | 28 / 33 / 33 |

All strict visibility/fade gates still fail. Reports:
[live](../build/room-entry-total-live-233/index.html),
[word-copy parent](../build/room-entry-total-word12-233/index.html),
[hidden DMA](../build/room-entry-total-hidden-dma-238/index.html),
[hidden DMA + scan](../build/room-entry-total-hidden-dma-scan-240/index.html).
This measures each room's own state edges, not boot offsets or independently
evolving combat-state equivalence.

## Two bounded experiments, no release claim

Scanning all rows with the twelve-row parent leaves visibility at 11/11/11
and introduces one approximately two-frame stable park packet gap:
[entry](../build/room-entry-total-word12-scan-235/index.html),
[park failure](../build/alias-word-12-scan-park-audit-235/index.html).
It is not advancing by itself.

New opt-in `--experimental-hidden-dma` permits 4096 VRAM bytes only in
transition state 2, after forced blank is asserted. State 0/1 retain 2048;
one CHR job per invocation, row scanning, final timing checks and complete
initial-publication requirements are unchanged. Default remains off. The
default-off rebuild is byte-identical to the word-copy parent 230.

[Executed DMA oracle](../build/hidden-dma-oracle-237/report.json): six cases
cover enabled/disabled in states 0/1/2, real CHR and row transfers, a full
12-KiB VRAM readback, all 128 row flags and initial requirements, the remaining
budget, cursor and transition barrier. Deliberately leaking into state 1,
using the wrong state-2 allowance, and omitting forced blank all fail actual
readback/state checks. No timing claim follows from these functional tests.

The 4096-byte candidate and its full-scan variant both pass stable park
packet timing, but neither improves first scenery visibility (12/11/11):
[DMA park](../build/hidden-dma-park-audit-238/index.html),
[DMA + scan park](../build/hidden-dma-scan-park-audit-240/index.html).
The larger transfer budget can retire rows earlier while the palette is
still black. Passing stable park timing does not certify load-time scheduling
or acoustic fidelity.

Candidate hashes:

- `hidden-dma-4096-native-236`: `d6a2c76fef38da53827a945c902d028e8cbb20bcefe46211b0ff013e0003da2a`
- `hidden-dma-scan-native-239`: `1ba21abf2d164e0e1a1af531ac4b3b97ca3158706f6e24cdc0e58e6e1b389f80`

## Why the palette starts late

Original fixed-bank code calls its fade service E343 from main-loop F2B4.
It uses `$3E`, `$0692` and `$0693`; palette generation fills `$0110..$012F`,
and the NMI's E461/E477 service copies those colors. This is confirmed by
disassembly of the local original ROM, not guessed from image brightness.

In room 2, NES initializes the fade at enable-relative frame 2 and changes
the palette at frame 6. The combined candidate initializes it at frame 6 and
changes colors at frame 9. Its `$010B` NMI tick accumulator reaches 4 while
the first main iteration is still unfinished. The fade routine itself has
not been accelerated or rewritten.

[Instruction/interrupt accounting](../build/room-fade-nmi-profile-244/report.json)
isolates the first F293 -> EFD4 -> F296 sprite-list call. The original return
PC and stack match; bound NMI-entry events are paired with RTI and verified
emulation-stack restoration. All 9,411 frame telemetry rows and full PCM
match a fresh normal-core replay (`hidden-dma-scan-normal-242`).

| First sprite-list call, raw frames 5662–5666 | Master clocks |
| --- | ---: |
| Inclusive elapsed | 1,332,320 |
| Four ordinary NMI spans | 1,243,684 |
| Outside those NMI spans | 88,636 |
| Subsequent sprite-list call, no intervening NMI | 62,206 |

**About 93% of the long first call is interrupt work.** The first three NMI
spans consume 349,696 / 337,908 / 341,052 clocks each, close to an entire
357,366-clock nominal frame. Thus attributing the 3.7-frame inclusive span
to slow sprite drawing would be incorrect. Residual time is not an exact
exclusive CPU-cycle measurement; DMA and other events can still contribute.

The next target is loading NMI producer cost and main-thread CPU availability,
while preserving the original fade, immutable queue ownership and audio
service. Faster row retirement alone does not establish faster visible loads.
Python suite: **356 tests pass**. Whole-game speed, dense alley coverage and
physical gameplay popping remain open.
