# Original camera deadline versus added port NMI work

The original-NES observer `tools/fceumm_scroll_trace.inc` records camera
and PPU writes without emulated accesses or timing changes. Separate core
`.deps/fceumm/rcr_nes_scroll_libretro.so`, capture
`build/nes-scroll-writes-01/nes`, CSV `build/nes-scroll-writes-01.csv`.
Its 7532-frame timeline and full WAV are byte-identical to the stock-core
`shop-exit-route-01/nes` reference.

At original driver frame 6812, E2B1 stores camera 110 at scanline 21.
The first raster IRQ writes horizontal scroll 110 through FCA4/$2005 at
scanline 30. At frame 6810, camera 108 is written at scanline 18 and applied
at line 30. Thus these moving-mall reference screenshots genuinely use the
new camera before the street band. This is not solely an ambiguity of
end-of-frame RAM versus screenshots. Across the whole observed range,
179 of 290 camera writes are before line 30; not all scenes/updates share
that timing, so do not impose it as an unconditional whole-game invariant.

## Port stage attribution

A host-only PC observer on the exact retained `literal-tail-buffer-01`
ROM logs `build/scroll-stage-01.csv` (raw core frames 6808..6834). It samples
entries/returns at the addresses below, with frame, line, cycle, PB:PC,
task and NMI depth. The full 7552-frame timeline/WAV match the stock-core
capture byte-for-byte.

| Stage / exact PC in this ROM | Frame 6829 line | Frame 6830 line | Frame 6832 line |
| --- | ---: | ---: | ---: |
| Original NMI reaches translated return, Cx:28C2 | 21 | 29 | 21 |
| Audio publication entry, C0:8136 | 45 | 65 | 38 |
| Audio publication return, C0:8176 | 59 | 78 | 51 |
| Graphics preparation entry, C0:8177 | 59 | 78 | 51 |
| Graphics preparation return, C0:819A | 110 | 159 | 125 |
| Camera store, Cx:E2B1 | 111 | 228 | 178 |

The original NMI return hook runs FA54/FF29 sound processing before the
audio transfer, then calls full graphics preparation before restoring the
interrupted main thread. In these frames, that added work holds the game
well past the original first-raster-split deadline. The camera sometimes
also has additional original main-thread work after the return.

This explains why refreshing the table at NMI exit only partly reduced the
observed lag. A proper fix must reschedule sound/graphics preparation around
the original camera/IRQ sequence, preserve bounded publication, and keep
audio servicing exactly once per intended game tick. Neither predicting
camera motion nor blindly rewriting a currently displayed band is adequate.
No scheduler implementation or Rival deployment was performed in this run.
