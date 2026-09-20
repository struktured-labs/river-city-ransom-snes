# Compact direct-row lookup: measured saving, still not deployable

The optional hidden-direct-row path now uses one 64-byte table to duplicate
tile high bytes. A selected attribute nibble chooses two pairs of palette
bytes. The pattern-table selector is duplicated once per row, then ORed into
each pair. The ordinary visible and rendering-off conversion paths, original
graphics, immutable staged rows and retirement semantics are unchanged.

This replaces five instructions in each of sixteen pairs with seven setup
instructions per row. Only sixteen nibble values are distinct; the initial
two-256-entry layout was unnecessarily large and exceeded the production ROM
segment by 1,697 bytes. That build (`hidden-high-lookup-303`) failed to link.
Its concurrently running oracle was interrupted and is **not evidence** for
the compact implementation. A fresh complete run validates the final source;
the harness now rejects source changes during a run.

## Executed correctness and equal-output timing

- `hidden-high-lookup-oracle-304`: 1,856 actual-VRAM cases exercise all 256
  source attributes, both mirroring modes and pattern halves, and all alias
  ownership states. Eight transition-state 0/1 controls retain the old staged
  path. Six mutants are rejected: queued overwrite, wrong high port, missing
  forced blank, wrong source bank, wrong lookup bits and missing pattern
  selector. All original shadow, staging, requirements and flags are checked.
- `hidden-high-lookup-timing-307`: eight paired tests use the **already built**
  old oracle-284 and new oracle-304 ROMs. Their hashes, labels and normal-core
  WRAM are bound by their original reports; the old implementation is not
  reconstructed from memory. Both arms' full WRAM matches the observer, and
  actual VRAM/ownership arrays match between arms. Every measured complete
  one-row stage saves **1,634 master clocks**, including direct DMA.
- `hidden-high-lookup-load-audit-307`: first five room-2 ten-row stages cost
  88,926–89,402 clocks. The prior candidate's corresponding observed stages
  cost 105,346–105,834 (`late-prepare-load-rows-307`). Complete 9,410-frame
  timelines and PCM match each candidate's normal-core replay. These game
  stages are measured workload samples, not a full-game speed ratio.

## Combined candidates and unresolved gates

The FastROM uploader was retested with early audio and the late-preparation
guard. Candidate `early-fast-publisher-300`, SHA-256
`b6d7e4c964171a0c426ffa4604f1ce8b81b9f641ab41e1ee8b69d227e57eba70`,
passes the full park packet gate (`early-fast-publisher-park-audit-302`),
unlike the older combination in [the previous experiment](FAST-PUBLISHER-EXPERIMENT.md).
A fresh nine-pair bridge/VRAM oracle plus four mutants passes in
`early-fast-publisher-oracle-301`. Room timing remains 9/8/9 versus NES 7/7/7.

Adding the compact lookup produces `hidden-high-lookup-304`, SHA-256
`fce995887fb8b46d7e5c18453efab84eb66622aaf87f49d37fa2e8229c323856`:

| Evidence | Result |
| --- | --- |
| `hidden-high-lookup-park-audit-306` | Zero stable park packet intervals over 1.5 frames, no native faults. |
| `hidden-high-lookup-neutral-audit-307` | Zero late observed NMI-entry intervals; full 9,410-frame timeline and PCM equal normal replay. |
| `hidden-high-lookup-entry-audit-306` | **FAIL**: scenery 9/8/9 versus NES 7/7/7; room-change-to-visible 26/31/31 versus 20/31/30. Fixed-offset fade mismatch remains. |
| `hidden-high-lookup-scroll-audit-306` | **FAIL** coverage: common positions 259/83/110/20 in rooms 0/1/2/3; minimum remains 64 each. All 472 compared scenery bands match and no late scroll publication occurs. |

The shorter park coverage is explicitly retained, not hidden by the passing
packet gate. Ordinary-input enemy evolution differs across candidates; these
results do not establish complete encounter, speed, scrolling or acoustic
fidelity. No new physical audio validation, controller-preset enablement or
Rival deployment has occurred. Rival remains on branded `765052c`.

## Next measured target: palette copy and publication latency

`late-prepare-palette-audit-302` updates the old palette diagnosis using exact
candidate 294, not the older 265 timing. Complete timeline and PCM are neutral:

| Room | First NES / SNES generation | SNES shadow + prepared colors | NES / SNES scenery |
| --- | --- | --- | --- |
| 1 | 6 / 7 | 8 | 7 / 9 |
| 2 | 6 / 6 | 7 | 7 / 8 |
| 3 | 6 / 7 | 8 | 7 / 9 |

The refreshed first main-iteration profile (`late-prepare-load-profile-301`)
now measures EFD4 at 320,486 inclusive clocks, including 227,556 in ordinary
NMI; the `$8000` update takes 49,980 without an interrupt. Earlier, much larger
main-thread timings no longer describe this candidate.

`late-prepare-palette-copy-profile-308` binds the actual `$E477` loop to the
same neutral instruction trace. It requires all 32 original indexed loads
in order and a matching stack at `$E482`; five unit cases reject truncation,
missing bytes, wrong stack and wrong opcode. The first fade's copy starts at
raw frame 5667 line 8, ends at line 51, and costs **58,096 master clocks**.
These clocks include adapter work/events; they are not NES execution time.
The color-generation, PPU-shadow, preparation and physical publication
boundaries must remain distinct in the next optimization. Simply reducing
hidden row cost has not removed the extra palette-display frame.
