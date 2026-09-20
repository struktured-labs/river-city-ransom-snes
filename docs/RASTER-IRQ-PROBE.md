# Isolated vertical IRQ probe

`tools/check_raster_irq.py` builds an asset-free cartridge from
`snes/raster_irq_test.asm`. It executes in the stock Snes9x core and checks
WRAM results after 120 frames. Evidence: `build/raster-irq-05/report.json`,
with per-variant ROMs, RAM dumps and capture receipts.

The normal case programs vertical IRQ line 30. The delayed case leaves
CPU IRQs masked until the latched vertical counter reaches 60. Both cases
actually enter the handler at lines 30 and 60 respectively. Reading TIMEUP
first sees its pending bit, and the next read sees it cleared. The handler
disables further IRQ generation, so this is a single-shot test, not a
recurring frame scheduler.

Sentinels verify 16-bit A/X/Y, carry and decimal flags, native register
widths, interrupt enable restoration, DB=$7E, D=$1234 and S=$1FFF after
return. The completion marker also requires execution to resume normally.
Two real instruction mutations omit the first TIMEUP read or clobber X
after restoration. They fail exactly the acknowledgement or X checks.
The probe now also enters IRQ from emulation mode, preserving the hidden
accumulator B byte and returning to the page-one stack. Both normal and
delayed emulation-mode cases pass.

Two nesting cases keep IRQ work active until NMI at line 225, starting from
native and emulation mode respectively. NMI occurs while the IRQ handler is
in native mode. Separate worker sentinels verify the interrupted IRQ's
A/X/Y, flags, DB and D, not merely the main thread's restored values. A third
negative control corrupts X in NMI; only the worker X check fails, proving
the outer IRQ restoration cannot hide that defect from this oracle.
All nine expected outcomes pass. `index.html` summarizes the results.

Run:

```
python3 tools/check_raster_irq.py \
  --core /tmp/rcr-snes9x/libretro/snes9x_libretro.so \
  --out build/raster-irq-NEW
```

This covers isolated emulation-mode entry/return and native NMI nesting,
not the production game's coroutine stack transformations or interrupt
bridges. It does not cover recurring service accounting, bank-switch
critical sections, DMA deadlines or audio fidelity. Those remain prerequisites to integration;
the production game scheduler and Rival deployment are unchanged.
