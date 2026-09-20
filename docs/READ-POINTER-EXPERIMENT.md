# Rejected read-pointer dispatch experiment and loading attribution

`build/read-pointer-dispatch-01` skipped constructing a shadow-memory
pointer before resolving CHR ROM in `ppu_read_buffer`. Non-CHR reads kept
normal nametable/palette handling. The adapter suite passed, including
buffered-read, palette, increment and negative controls. However, baseline
remained 1982 frames, with exactly the same transition durations as
`audio-exit-01`: 177/62/64/479. The runtime change was reverted.

Comparing original RAM task `$0100` during settings/story against the port
provides a more useful next target. Original `movement-probe-02/nes` and
current `audio-exit-quality-01/snes` share the same input prefix and phase
definitions. Both spend the first 21 frames of each phase at task zero.
Later task-$80 runs are 1 and 2 frames for original settings versus 2 and
7 for SNES; original story has runs 1 and 2 versus SNES 2 and 9. Remaining
task-zero spans are also retained, not subtracted from benchmark totals.

SNES frame-boundary PCs during these longer task-$80 runs map to
`bulk_ppu_byte`, `ppu_read_buffer`, `ppu_pointer`, `nametable_pointer`,
`mark_ppu_dirty` and `dirty_mirrored_row`, as well as the original C864
decompressor. PPU rendering is disabled and adapter NMI depth is zero in
those samples. These are boundary observations, not an instruction-cycle
profile. They point to translated decompression/I/O work as the next
investigation target rather than reducing the game's matching initial wait.

No retained ROM change or hardware deployment. Current candidate remains
`audio-exit-01`; its two unresolved loading gates and audio-fidelity
limitations are unchanged.
