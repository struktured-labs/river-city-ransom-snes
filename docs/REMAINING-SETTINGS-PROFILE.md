# Remaining settings PPU traffic after repeated-fill batching

Profiled retained ROM `build/repeat-shared-01/native-cpu.sfc` with the
host-only instruction observer documented in `RECT-OUTER-PROFILE.md`.
Capture: `build/cpu-repeat-shared-settings-01/snes`, 1967 frames.
CSV: `build/cpu-repeat-shared-settings-01.csv`, raw frames 240 through 320.
Both timeline and full WAV are byte-identical to the normal-core capture
`build/repeat-shared-quality-01/snes`. The observer has not shifted this
replay's timing or audio.

For raw frames 250 through 320 inclusive, the current repeated-fill engine
has only 14 entries; `bulk_ppu_byte` has 52. By contrast, `ppu_write_data`
has 467 entries and `ppu_pointer` 891. These are instruction/entry counts,
not cycle measurements or proof that every call lies on a critical path.

Counting execution at the original patched call sites distinguishes callers
that share an adapter stub:

| Original instruction | Executions |
| --- | ---: |
| FCF7: STY $2007 | 192 |
| E47A: STA $2007 | 192 |
| E5F0: STA $2007 | 32 |
| C7CD: STA $2007 | 8 |

The remaining 43 ordinary stores originate in BBxx code. FCF7 and E47A
therefore account for 384 of the 467 ordinary destination writes in this
window. This points the next investigation at their complete original loops,
not more unrolling of the already accelerated page loop. Their semantics,
interruptibility, and critical-path contribution still need inspection before
implementing replacement helpers. No speed gate was relaxed and no hardware
was reloaded.
