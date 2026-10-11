# Build 4295: hard-freeze fix and Gamer stamina bar

Base: build 4294 (`rumble-wip` 235d561). Build: `build/freeze-fix-4295/native-cpu.sfc`,
SHA-256 `e1b81f7df83b74ed7bd17d4d8f3602c489649e44f3d0ca1d72f7947bb1c0f596`.
Produced by `tools/build_freeze_fix.py` (byte-exact delta over 4294, checked).

## The freeze

Symptom: during a room change mid-fight, the game hangs forever in the NMI tail
`@outside_vblank: lda $4212 / bmi` (C5:339x in `snes/nmi_return_tail.inc`), with DB=$C5 or DB=$43.

Root cause: several helper layers read their own lookup tables with
`phb / phk / plb ... plb`. For a few instructions DB is then the program bank ($C1-$C8)
while NMI and the raster IRQ are enabled. The NMI handler and the translated game use
absolute addressing and assume DB is a system-area bank ($80-$88), where $2100-$43FF are
hardware registers. An interrupt landing inside that window therefore talks to ROM instead
of the hardware:

* NMI with DB=$C5: `stz $4200`, `lda $4210` etc. hit ROM; the tail reads `$4212` from ROM,
  which holds a byte with bit 7 set, so "wait for vblank to end" never finishes (DB=$C5 hang).
* Raster IRQ with DB=$C5: `lda $1C02 / sta $1CA6 / jml [$1CA4]` reads/writes ROM and jumps to a
  stale bank; execution runs into data at C6:A3F4 where `44 43 44` is an `MVP` that sets DB=$43,
  and ends in the same loop (DB=$43 hang).

A room change is where the game spends the most CPU time with NMIs landing at arbitrary points,
and several of the windows are hit every frame in a fight (`add_skill` runs per spawn/hit,
`name_paint` per HUD refresh, rumble `start_pulse` per hit), which is why it shows up there.

Proof (Mesen2, `dbtrace.lua` hooking NMI $00:80FB and IRQ $00:8222): on 4294 the hanging runs
show exactly one interrupt entered with DB bit 6 set, interrupting C5:708F (inside `add_skill`
right after `phk/plb`) or C5:6BCC-6BCE (rumble `start_pulse`), followed immediately by the hang.
snes9x hang records end at native PC C5:708E. On 4295 no interrupt ever enters with a bad DB.

Introduced by commit a4c3e2c (2026-09-20, "Implement Intermediate and Gamer Mode on native
4146"), i.e. the first difficulty-mode builds after 4146. Each later layer added windows:
PHK/PLB windows in the helper slots were 0 in 4146, 32 in 4260, 40 in 4292 (Gamer outline
`name_paint`) and 48 in 4294 (rumble `start_pulse`). Builds with no windows (4108, 4146)
never froze; every build with windows did (freeze odds depend on how often a window is hit
in a given run, not just the window count).

Sites (each present in banks 1-8): `name_paint` $696E, `start_pulse` $6BCC, `add_skill` $708C,
`menu_next` $70DE, `menu_prev` $70F4, `paint_skill` $714B (dead, kept consistent).

The base runtime's own DB=$7E sections (C0:200A-321B) run inside the NMI publisher with
interrupts masked, so they are not a hazard (confirmed: 0 bad-DB interrupt entries in the
4295 Mesen batch).

## The fix

No helper changes DB any more. Tables are read with long addressing
(`lda f:$C10000+table,x`), so DB stays whatever the game had. Every label keeps its
address and every helper keeps its size (padding with `nop`), so no caller moves.
`add_skill` reads the spawn table long from bank $C5 (`adc f:$C5B946,x`).

Guard rails: `tools/build_freeze_fix.py` refuses to build if any `4B AB` (`phk; plb`)
appears in $6900-$7200 of banks 1-8, and `tests/test_freeze_fix.py` rejects
`phk/plb/mvn/mvp` in the helper sources.

No defensive timeout was added. By the time the tail loop spins, the whole NMI has already
run against ROM (and the IRQ variant has jumped into data), so a timeout would only resume
the game in a corrupted state. The loop itself is correct when DB is correct.

Timing rules: the changes are inside existing helpers, run at the same point as before, cost a
few cycles at most (long reads are +1 cycle each, the phb/phk/plb/plb they replace cost 14),
and nothing moved into the screen-update window. `stam_ticks` starts with `php / sep #$30`,
so register widths are fixed at hook entry.

## Gamer stamina bar

NES HUD code (bank 0 $BB86) draws `(stamina + 7) >> 3` ticks capped at 16 (8 cells x 2 ticks).
In Gamer mode stamina goes up to 255, so 128-248 drew full and 249-255 wrapped (`+7` overflows)
to no bar. `snes/stamina_bar.asm` hooks $BB86 in banks 1-8 with `jsr stam_ticks` at $6D00:

* Novice/Intermediate/Advanced: the original code path, byte-for-byte (same as NES, including
  NES's own 249-255 blank, which cannot happen with the NES cap of 127).
* Gamer: 0 -> 0 ticks, else `((s - 1) >> 4) + 1` (1..16): monotonic, empty only at 0,
  full only from 241.

Verified by `tools/stamina_bar_sweep.py` (pokes each value 0-255 and measures the HUD bar
from screenshots) on NES, 4294 and 4295, and by a mini-CPU unit test that runs the helper for
all 256 values in every mode.

## Verification (details in `~/rcr-evidence/4295-freeze-fix/`)

| check | 4294 | 4295 |
|---|---|---|
| snes9x hang variants (66 runs) | 1 hang | 0 hangs |
| Mesen2 hang variants (60 runs) | 2 hangs | 0 hangs |
| bad-DB interrupt entries (Mesen) | present in hanging runs | 0 |

Earlier snes9x rates for reference: 4292 2/65, 4260 4/64, 4146 0/16, 4108 0/16.

Other checks on 4295:

| check | Mesen2 | snes9x |
|---|---|---|
| Gamer outline acceptance (9 checks) | 8/9 in the full run; check 9 passes on its own run (see below) | 9/9 |
| Rumble R0-R6 / S-checks | 7/7 | pass (plus street-offset variants 0/37/101) |
| Timing (street, NMI publish batches) | default: max vblank scanline 256, 0 in active display; Gamer: 257, 1 (4294: 257, 1) | 1P/2P cadence no worse than 4294 |
| Stamina sweep 0-255 | - | Gamer monotonic, empty only at 0, full from 241; Novice identical to NES |
| Unit tests | 1637 run, 1 pre-existing failure (`test_chromatic_wub`, also fails on 235d561) | |

Mesen check 9 in the full acceptance run: Alex did carry a goon (504 carried sprites, all
outlined), but the check's audit counters accumulate over all fight attempts and an earlier
attempt had logged a one-frame "red inside the composed body" for a goon holding a bat
(hand/arm overlap). None of the bytes that draw the outline changed in 4295 (the ROM diff
against 4294 is only the helper table reads, the stamina hook/helper and the checksum), and the
focused run (`RCR_ONLY_CARRY=1`) passes check 9 on 4295.
