# Opt-in IRQ-enable plumbing

`interrupt_policy.inc` centralizes the seven runtime enable-value loads.
Without `EXPERIMENTAL_RASTER`, it emits the original instructions exactly.
`build/irq-policy-default-01/native-cpu.sfc` retains SHA256
`9d72565ce36e59b77343cd9454128b07fec46e38635cded4641b4e0b8f5fca44`.

`build_native.py --experimental-raster` additionally ORs a WRAM IRQ-enable
shadow at $1CA2 into the hardware enable value. Ordinary generated stubs
still honor NMI-depth and paired-bank guards; their branch displacement
includes the extra instruction. The explicit PPUCTRL coroutine tail retains
its existing guard and VBlank wait, and preserves A/P around the new enable
calculation. No scheduler sets the shadow yet; it remains zero after reset.
Do not interpret this flag as a working raster scheduler.

The old rejected frame-poll experiment used $1CA2 for pending work. That
code was reverted; this field now means IRQ enable (0 or $20). Future service
accounting must use separate storage.

Validation:

- All 117 existing Python tests pass; three additional adapter-layout tests
  verify guarded branch targets, coroutine preservation sequence and default
  absence of shadow accesses.
- Eleven expected isolated IRQ outcomes pass in
  `build/raster-irq-policy-01/report.json`, including actual line-30 and
  delayed-line-60 IRQs enabled through the production macro with PPUCTRL=0
  and shadow=$20. The HTML report is alongside the JSON.
- The opt-in game build completes the baseline in 1956 frames, unchanged in
  total, but its full timeline and WAV are **not byte-identical** to retained
  baseline. Added instructions change execution timing; no equivalence or
  audio-fidelity pass is claimed. Capture: `build/irq-policy-baseline-01/snes`.

Remaining integration: arm the raster timer, dispatch safely into the active
game bank, separate coroutine returns, move work with explicit once-per-tick
accounting, and update scroll state by its deadline. Then rerun moving-camera
pixel audits, original-speed gates and received-audio/service tests.
Default game behavior and Rival deployment are unchanged.
