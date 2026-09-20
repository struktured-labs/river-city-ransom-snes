# Camera writes occur after the street band begins

`build/scroll-writes-01/snes` replays the retained `literal-tail-buffer-01`
ROM with a host-only observer of camera and HDMA table stores. The full
timeline and WAV are byte-identical to `literal-tail-long-normal-01/snes`.
Observer fragment: `tools/snes9x_scroll_trace.inc`; core built separately
as `/tmp/rcr-snes9x/libretro/rcr_scroll_trace_libretro.so`.

`build/scroll-writes-01.csv` columns: raw core frame, scanline, CPU cycles,
NMI counter, PB:PC (hex), opcode (hex), target (hex), prior target value,
A, X, Y. These are pre-instruction observations, not post-store timestamps.
The observer adds no emulated accesses/cycles and covers raw frames 6500..7100.

In the moving mall section, original E2AA writes the camera's high bit to
$3D and E2B1 writes its low byte to $F6. Representative actual low-byte
updates and later publication:

| Raw frame | Scanline | Store | Value |
| --- | ---: | --- | ---: |
| 6829 | 111 | Game F6 | 106 |
| 6829 | 254 | HDMA table 1C94 | 106 |
| 6830 | 228 | Game F6 | 108 |
| 6830 | 252 | HDMA table 1C94 | 108 |
| 6831 | 253 | HDMA table 1C94 | 108 |
| 6832 | 178 | Game F6 | 110 |
| 6832 | 253 | HDMA table 1C94 | 110 |

The game can therefore compute the next camera after the street's scanline-32
band has started. A table refresh at NMI exit cannot reliably pick up that
future write, and modifying the active band late would not restore the
already-rendered pixels. Do not compensate with predicted velocity or a
fixed two-pixel offset.

This refines the prior frame-boundary diagnosis: publication does catch up
at the next VBlank; late original-game computation is involved. The remaining
investigation must compare original NES camera/IRQ timing and locate the
port's late-update work, not assume a pure table-copy bug. Raw-core frame
numbers must not be equated blindly with NES or driver callback boundaries.
No new runtime change or Rival deployment.
