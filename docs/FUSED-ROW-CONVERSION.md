# Fused mirrored-row conversion — experimental, not deployed

Rival remains on `765052c`. This change reduces actual row preparation cost,
but does not yet meet original room-entry/fade timing or full-game fidelity.

## Implementation and ownership

`--experimental-fused-alias-rows` requires attribute lookup and defaults off.
During conversion it stores each completed tile word into its mirrored row
only when that alias is dirty state 1. States 0/2/3 remain untouched: in
particular, a staged snapshot awaiting DMA is immutable even when a newer
shadow write exists. Alias-ready is published only after all 32 words are
stored. The redundant subsequent alias-copy call is omitted in this mode.

Eight attribute groups are unrolled with fixed row-relative destination
offsets. X advances once at the end rather than twice per tile. Original tile
indices, pattern-half selection, palettes, mirroring and source shadow bytes
remain unchanged. The producer still runs behind the existing native bridge's
interrupt guard. No PPU writes, queue-barrier relaxation or game-state edits
are introduced by this converter.

The extracted single-group macro preserves the old non-fused store-offset
path. A default-off game rebuild is byte-identical to parent 239. The existing
source-level store test now follows that extracted macro and retains its
original flag/store assertions; executed full-row checks also pass.

## Executed oracles and measured cost

[1,856-case snapshot oracle](../build/fused-unrolled-all-attributes-255/report.json):
29 source rows × two mirroring modes × two pattern halves × four alias states
× four shadow patterns. Every case checks all 8,192 staging bytes, all 128
queue flags, unchanged original shadow, and data-bank/direct-page restoration.
The selected rows' **actually consumed** attribute addresses cover all 256
byte values. Three assembled mutants fail: overwriting queued aliases, shifting
alias destinations, and losing the ready flag.

Coverage was explicitly corrected during development: the earlier 1,536-case
matrix covered only 96 consumed attribute values, despite its initial scope
wording. Its retained report is annotated; the expanded matrix and a unit test
now derive coverage from selected physical row addresses, not from unused
bytes elsewhere in the fixture.

Sixteen full-conversion cases additionally check all 3,840 visible tile words
with the ten-row budget, both pattern halves/mirrors/tasks, and the separate
store-offset option off/on:
`build/fused-unrolled-ten-full-rows-257` and
`build/fused-unrolled-offset-full-rows-257`.

[FastROM timings](../build/fused-unrolled-row-timing-250/report.json) measure
the complete one-row preparation stage, including dispatch and bookkeeping.
Dirty aliases save **2,930–2,942 master clocks**; measured queued states 2/3
save **1,348**. Each timing arm matches its normal-core full-WRAM control.
These are helper measurements, not whole-game speed ratios.

The first looped prototype saved only 1,144–1,162 clocks and added 392 clocks
for queued aliases. Removing duplicate dispatch and unrolling resolved that
measured overhead. Its game replay also had a 1.58-frame stable park packet
gap, so it is not a deployment candidate:
[retained failure](../build/fused-rows-park-audit-249/index.html).

## Integrated results

| Candidate | First scenery after render-enable, rooms 1/2/3 | Total from room change | Stable late park packets |
| --- | --- | --- | ---: |
| NES | 7 / 7 / 7 | 20 / 31 / 30 | not SPC transport |
| Fused/unrolled, twelve-row budget | 11 / 11 / 11 | 28 / 34 / 33 | 0 |
| Fused/unrolled, ten-row budget | 11 / 10 / 11 | 27 / 33 / 33 | 0 |

Both include the previous experimental 4096-byte hidden DMA and full hidden
queue scan. Neither passes the strict visibility/fade gates:
[twelve-row entry](../build/fused-unrolled-entry-audit-252/index.html),
[ten-row entry](../build/fused-unrolled-10-entry-audit-253/index.html).

The ten-row candidate passes:

- [Park packet cadence](../build/fused-unrolled-10-park-audit-253/index.html).
- [Full replay observer neutrality and loading row spans](../build/fused-unrolled-10-load-spans-256/report.json):
  all 9,409 timeline rows and PCM match the normal core. Five complete ten-row
  hidden batches measure 124,346–124,802 clocks. Twelve-row fused batches in
  capture 250 measure about 149,000 versus the parent's roughly 185,000.
- [Present Status](../build/fused-unrolled-10-status-audit-257/index.html):
  both entries have zero mismatching pixels and correct numeric values.
- [Short rightward movement](../build/fused-unrolled-10-movement-audit-257/index.html):
  the fixed original probe passes without timing alignment.

Candidate SHA-256 (`build/fused-unrolled-10-native-251/native-cpu.sfc`):
`9c4dabb1ce774271d5eeefe94b210b56c7c387450c01fe17a945cc511a7dd500`.
Twelve-row SHA-256: `db55b63eaaed604531d0587de117a6dc5161ddbf421f70c5843cc47e9cb13785`.

Python suite: **359 tests pass**. Café/pause integration for this exact ROM,
full-game speed, remaining scrolling coverage and physical gameplay audio
remain unverified. No restart or physical popping claim.

Next work must remove more loading CPU cost without merely delaying the
render-enable edge. A possible larger change is separate low/high tilemap
staging planes, allowing direct tile-byte copies and two bounded DMA passes;
that is only a design possibility, not implemented or certified here.
