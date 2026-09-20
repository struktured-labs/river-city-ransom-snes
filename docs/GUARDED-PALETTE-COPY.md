# Guarded palette-copy hook: actual game cost reduced, fade still late

Candidate `build/palette-copy-on-311/native-cpu.sfc`, SHA-256
`5de6fdf763af8dd04baa868831ca275dea3a114dbea194d83b2f80ab7db9e91f`,
is **not deployed**. This is a default-off experiment, not full-game acceptance.

## Production change

`experimental_palette_copy` replaces the original `$E477` indexed load with
a jump to `palette_copy_loop`. The builder checks all eleven original loop
bytes (`BD1001 8D0720 E8 E020 90F5`) and records the hook/preimage in the
manifest. The already translated `$E47A` PPUDATA store remains the fallback.
Default-off `palette-copy-control-311` is byte-identical to parent 304.

The batch requires X=0, PPU address `$3F00`, increment one, decimal mode off,
and either existing NMI/bank ownership or disabled NES NMI. Otherwise it
executes the displaced original load and resumes the scalar loop. It does
not postpone an interrupt that the scalar path could have delivered between
bytes. Guards are checked before masking hardware NMI.

The guarded path performs all 32 original reads and writes in ascending order.
The four sprite-transparent entries alias background offsets 00/04/08/0C;
unused physical offsets 10/14/18/1C retain their old values. It preserves Y,
DB, DP, PB, stack and final status flags, reproduces A/X and hidden accumulator
B, advances the PPU address and write counter, and leaves row ownership alone.
It changes no palette indices, art or game fade logic. Original code still
clears the palette dirty flag after the hook returns to `$E482`.

This differs from claiming the historical [palette-batch experiment](PALETTE-BATCH-EXPERIMENT.md)
passed the current gate: that old implementation was reverted and lacked the
current mutation, timing and full-route evidence. Both experiments' lack of
room-visibility improvement remains explicit.

## Executed helper evidence

`palette-copy-oracle-311` contains **59 paired cases** using the actual
production adapter for the original scalar arm and the hook for the other.
The 48 eligible combinations vary input bytes, overflow flag, counter wrap,
and the three ownership conditions. Eleven fallback cases cover nonzero and
wrapping X, other palette/nametable addresses, increment 32, decimal mode and
unowned enabled NMI. The fixture enters with nondefault DB/DP and checks full
source/shadow regions, row flags, relevant state and saved caller registers.
Eligible palette output also has an independent alias oracle.

Five executed mutants fail: wrong transparent alias, short write count, lost
overflow flag, wrong final address and ignored stride guard. Compilation
failures are not accepted as successful mutation rejection. The first smoke
fixture's header was one byte too long; it was corrected before the successful
fresh smoke-310 and full oracle-311 runs.

`palette-copy-timing-313` replays both already-oracled ROMs for **all 59 cases**
and verifies their bound ROM/WRAM hashes. Read-only observations must leave
all WRAM identical. Actual fast-path entry occurs exactly once when eligible
and never otherwise. Eligible complete loops save **56,556–58,198 master
clocks**; unsupported loops incur **112–4,008 clocks of guard overhead**, which
is retained in the report. This is path-selection evidence, not exhaustive
pending-hardware-NMI race injection.

## Actual game execution and regression gates

`palette-copy-game-profile-316` binds candidate ROM/manifest, instruction trace
and a normal-core replay. It checks the hook in all eight replicated banks,
each observed entry, all 32 source/destination pairs against actual ROM
operands, and the original return stack/X. All **four room-2 palette loops in
the observed window cost 2,730 clocks each**. The earlier candidate's first
loop cost 58,096 clocks (`late-prepare-palette-copy-profile-308`); paired helper
tests above isolate the optimization from other candidate differences.

| Evidence directory under `build/` | Result and scope |
| --- | --- |
| `palette-copy-park-audit-313` | Zero stable park packet intervals over 1.5 frames; no native faults. |
| `palette-copy-neutral-audit-314` | Zero late observed NMI-entry intervals; complete 9,410-frame timeline and PCM identical to normal core. |
| `palette-copy-audio-audit-314` | 9,236 acknowledged packets, one per completed NMI, no unfinished tail, byte mismatches or unflushed CPU writes. Full PCM and transition-gap clips retained. Not a subjective/physical no-pop verdict. |
| `palette-copy-status-audit-315` | Both Present Status entries match NES with zero mismatching pixels. |
| `palette-copy-movement-audit-315` | Short fixed-input movement passes; 21 pixels on both systems. Not combat or full-game speed. |
| `palette-copy-entry-audit-313` | **FAIL**: first scenery 9/8/9 versus NES 7/7/7; whole loads 26/31/31 versus 20/31/30. Fixed-offset fade gates still fail. |
| `palette-copy-scroll-audit-313` | **FAIL** coverage: 259/83/110/20 common positions; minimum is still 64 each. All 472 compared bands match, with no late publications. |

401 Python unit tests pass, separate from the executed cartridge matrices.
New instruction-audit tests reject missing pairs, wrong aliases and wrong
source addresses. All evidence stays on the private loopback review server.

## Remaining target

Faster copying did not remove the extra palette-display frame. The consumer
uploads prepared colors before the original NMI writes the newly generated
palette shadow; later conversion waits for a subsequent upload. The prior
neutral palette trace also shows one extra generation frame in rooms 1/3.
Publication ordering and original NMI gating must be examined together; do
not accelerate the game's fade counter or merely align screenshots to pass.

Dense park scrolling coverage, café/pause integration on this exact candidate,
full original-speed parity and physical gameplay audio remain incomplete.
No Rival restart: live branded `765052c` is unchanged, with controller presets
still disabled there.
