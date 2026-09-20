# Original decompressor call-site profile

`tools/trace_nes.lua` now emits `decompression.jsonl`: every original C8DB
source-read and C90C destination-write entry records the immediate
predecessor PC, frame, source base/index, destination, byte and PPUCTRL.
It uses the existing execution callback, so nested commands do not inherit
an incorrect global last-command classification. Physical PRG offsets
select the actual helpers rather than merely matching a CPU address.

Run: `build/decompression-profile-01`, 1300 original FCEUX frames replaying
the verified `movement-probe-02/nes` inputs. Its manifest hashes the new
event file and binds the input capture and original ROM. This is command
frequency, not CPU-cycle profiling. At frames 60, 120, 300, 600 and 900,
RAM, PPU and OAM snapshots are byte-identical to the older
`reference-shop-01` run with the same early input prefix.

| Destination write caller | Whole run | Settings phase | Story phase |
| --- | ---: | ---: | ---: |
| C861: repeated byte | 1348 | 190 | 410 |
| C875: literal bytes | 626 | 52 | 227 |
| C891: rectangular repeated byte | 3146 | 782 | 387 |
| Total | 5120 | 1024 | 1024 |

Phase columns use the original replay capture's explicit frame boundaries,
not an inferred alignment against the SNES. The new observations overturn
the tentative assumption that literal-byte traffic dominates settings.

An experiment at `build/rect-run-01` accelerated C891 repeated writes under
NMI-disabled, increment-one, zero-latch, nondecimal, ordinary-nametable
guards. It amortized adapter setup and marked only the first changed byte
of each eight-byte segment, retaining conservative attribute boundaries.
The benchmark nevertheless regressed from 1982 to 1990 frames:
177/62/64/487 instead of 177/62/64/479. Settings/story were unchanged.
Frame-boundary samples do reach the new helper, but do not establish its
total execution time or explain the regression.

That implementation and its ROM hook were reverted, without claiming a
semantic-equivalence pass. The per-call tracing remains. No hardware
deployment. Current candidate is still `audio-exit-01`.
