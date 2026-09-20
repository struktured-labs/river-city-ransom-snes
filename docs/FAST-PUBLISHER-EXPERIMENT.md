# FastROM video consumer — functional, not deployable

Hardware NMI enters bank `$00`. The producer already enters through `$C0`,
but the NMI's `publish_video` wrapper calls `native_video` with a same-bank
JSR. Consequently the consumer's ROM fetches remain in the slow mirror even
when MEMSEL is enabled. The new **default-off** `experimental_fast_publisher`
option uses a bank-$C0 JSL trampoline; its JSR runs the same consumer, and RTL
restores the bank before the wrapper restores the original interrupt state.
DB remains zero for MMIO. No DMA budgets, palette ordering, row semantics,
graphics assets or game logic are changed. The builder requires FastROM.

`fast-publisher-control-277` is byte-identical to its candidate-265 parent.
The opt-in ROM is `build/fast-publisher-on-277/native-cpu.sfc`.
SHA-256: `fd09361c5f53b712537445aa5203be2551316affdfd8f005d068a3e47c6e36e8`.

## Executed bridge and DMA oracle

[Nine paired cases](../build/fast-publisher-oracle-279/report.json) cover
transition states 0/1/2 and CHR transfers of 0/1024/2048 bytes. Both arms
enable MEMSEL, enter from bank $00, and execute the extracted production
bridge with nondefault D/DB and known A/P/X/Y/stack values. Tests read back
those registers, restored program bank and emulation bit; verify actual VRAM,
all generation flags, initial requirements, remaining byte budget and cursor;
and observe the exact linked consumer bank. Each arm's entire WRAM matches
an unobserved control. Four mutation controls cover wrong ROM mirror, wrong
CPU mode, lost DB and lost A.

| Hidden state-2 CHR bytes | Clocks saved, bridge entry through VRAM completion |
| --- | ---: |
| 0 | 8,836 |
| 1,024 | 7,044 |
| 2,048 | 4,980 |

State-1 savings are 8,234 / 4,522 / 480. These are equal-publication
comparisons. Visible state-0 paths may legally transfer more rows within the
same beam deadline, so their elapsed durations are not an equal-work speed
ratio. The measured span ends before final OAM/CGRAM service.

## Full game result: do not deploy

[Room-entry audit](../build/fast-publisher-entry-audit-278/index.html):
first scenery is 11/10/10 frames after rendering-enable, versus the parent's
11/10/11 and original NES 7/7/7. Whole room-change-to-visible times are
27/33/32 versus NES 20/31/30. All strict original timing/fade gates still fail.

[Park packet audit](../build/fast-publisher-park-audit-278/index.html): **four
stable unpaused packet gaps exceed 1.5 frames**, longest 728,044 clocks
(2.0373 nominal frames). The route completes without native faults in 9,410
frames. This candidate fails the audio transport timing requirement despite
the local CPU saving; the test is not being shortened or realigned to hide it.
Independently evolving combat means this is not proof that faster ROM
fetches themselves cause a slowdown in an identical encounter state.

[Complete observer-neutral replay](../build/fast-publisher-neutral-280/report.json)
matches all 9,410 timeline rows and full PCM against the normal core, so the
failed timing run is not an instrumentation artifact. The Python suite has
376 passing tests; nine paired executed bridge cases and four mutants are
additional emulator checks, not counted as unit tests.

Retained as an opt-in measured experiment, not a default or Rival update.
Further work must recover main-loop availability while passing the complete
audio timing route. Acoustic fidelity remains a separate unproven requirement.
