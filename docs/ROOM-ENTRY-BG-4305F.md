# Issue #8: room-entry background corruption (trial 4305f)

**Status: trial, DO NOT MERGE.** Defensive fix. The real-hardware symptom has
not been reproduced in Mesen2.

## Symptoms (MiSTer, about 50-75% through the game, after skill I -> G -> I)
1. The whole wrong scene is drawn (the previous area's BG) under correct
   HUD, sprites and menus.
2. Patchwork: mismatched BG tiles inside an otherwise correct scene.

Opening and closing the pause menu repairs both.

## Mechanism (why corruption can outlive a scene load)
- `ppu_write_data` skips bytes that are identical in the NES nametable shadow
  (`cmp [$00] / beq @unchanged`), so a row is only marked dirty when its
  shadow bytes change.
- On the render-on edge, rows that are clean (`$1D00,x == 0`) are trusted and
  not re-required (`$1E80,x`).
- The 24-slot CHR bank cache (`$1DA0`) likewise skips CHR uploads for banks
  it believes are resident.

So if VRAM ever diverges from the shadow while the shadow is marked clean,
nothing republishes it. Possible causes include a VRAM write that real
hardware drops outside VBlank or forced blank, or a CHR or tilemap upload
interrupted by a mode switch. Later loads keep the stale data wherever the new
scene's bytes match the old ones (symptom 2). If the cache or flags are wrong
for the whole map, the old scene stays up (symptom 1).

The pause menu repairs it because the menu writes *different* bytes over
every row and bank, which forces a full republish when it closes.

## Fix (tools/build_room_entry_bg.py, parent 4305e)
In every runtime bank 1-8:
- In the render-on snapshot loop, change `bne` to `bra` (`+0x280C`). Every
  visible row is now required at each scene load, exactly as after the pause
  menu closes.
- In the render-on edge hook (`+0x7F80`), call a new helper (`+0x7FA0`) that
  invalidates the CHR bank cache (`$1DA0` = `$FF` x24) and sets the CHR-dirty
  gate (`$1CBB`). Every load then re-uploads CHR.

Every scene load is now self-contained and repairs any earlier divergence.
The cost is that forced blank lasts about 3-5 frames longer per load.

## Evidence / tooling
- `tools/mesen/row_invariant.lua`: checks every frame that each clean row's
  VRAM matches the converted shadow. Over ~80k frames of stress play there
  were only transient violations, all repaired within about 20 frames (for
  example, dialogue text written by `C7:30A3`). There were none on 4305e or
  4305f.
- `tools/mesen/vram_timing.lua`: found no VRAM writes during active display.
  The latest DMA ended on line 256.
- `tools/mesen/room_bg_loads.lua`: runs scene loads through pause submenus,
  skill changes through LEVEL (including I/G/I) and street play. It checks
  every visible clean row 30 frames after each load.
- `tests/test_room_entry_bg.py`: checks the patch footprint and the parent
  guard.
