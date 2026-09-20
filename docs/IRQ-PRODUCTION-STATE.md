# Production interrupt-state observation

Observed retained ROM `literal-tail-buffer-01` without modifying its bytes.
Host-only observer `tools/snes9x_irq_state_trace.inc`, separate core
`/tmp/rcr-snes9x/libretro/rcr_irq_state_libretro.so`, pinned Snes9x 7a8878f.
Capture `build/irq-state-01/snes` completed 7552 frames. Its full
`timeline.json` and `audio.wav` compare byte-for-byte equal to
`build/literal-tail-long-normal-01/snes` using `cmp`.

CSV `build/irq-state-01.csv` fields:
frame, scanline, cycles, PBPC(hex), task, NMI depth, I, E, S, D, DB, NMITIMEN.
Addresses are specific to the retained ROM; this is not a relocation-safe
observer for an edited build.

At frame 6808:

| Stage | Line | I | E | S | D | DB | NMITIMEN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Original NMI return C7:28C2 | 21 | 1 | 1 | 497 | 0 | 135 | 0 |
| Audio bridge C0:8136 | 38 | 1 | 1 | 494 | 0 | 135 | 0 |
| Preparation return C0:819A | 130 | 1 | 1 | 494 | 0 | 135 | 0 |
| Camera write C7:E2B1 | 186 | 0 | 1 | 509 | 0 | 135 | 128 |

The game does restore CPU IRQ acceptance in its main thread. Hardware
NMITIMEN still enables only NMI, so adding a CLI is not the missing fix at
these camera checkpoints. The runtime holds I set and hardware interrupts
disabled throughout added NMI work, then returns to the emulation-mode game.

Integration constraints confirmed by current source:

- `nmi_task_return` intentionally consumes the NES coroutine interrupt frame;
  it cannot share an ordinary IRQ epilogue.
- `nmi_rti_return` restores the ordinary saved Y/X/A and returns with RTI.
- Generated hardware stubs and runtime exits restore only PPUCTRL bit 7 to
  NMITIMEN. A raster enable added in one place would be lost on subsequent
  hardware accesses. All enabling paths need a consistent interrupt policy.
- Native interrupt vectors currently target a bare RTI. The isolated
  nesting probe is therefore not evidence that production nested NMI performs
  any publication or game service.

Next implementation must give recurring raster work explicit pending/served
accounting, preserve critical-section masking across adapters, and leave the
coroutine return path distinct. No production scheduling change or Rival
deployment is included in this observation.
