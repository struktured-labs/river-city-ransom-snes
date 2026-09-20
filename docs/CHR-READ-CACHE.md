# CHR read-pointer cache: one load frame saved, not deployed

Candidate `build/chr-cache-on-437/native-cpu.sfc`, SHA-256
`5403a85a4a817b0a78e542bd51e335f9dbb7776aa3fa9400a701e1a4389c8c02`.
The disabled build is byte-identical to sound-commit baseline 418,
`711681c49ca025d776bd546026328498dd9ddb7b5c2836ab830f8f132f5c4168`.
`experimental_chr_read_cache` remains default-off. No Rival restart or
hardware deployment occurred. This is a qualified scoped experiment, not
original-speed, whole-game, or acoustic acceptance.

## Change and ownership

The original game reads compressed room data out of CHR ROM through buffered
PPUDATA. The native adapter previously recalculated the mapper address on
every byte, even for consecutive reads in the same 256-byte page.

The cache keeps a valid bit, PPU high-page key and physical high/bank bytes
in private WRAM `$1B50..1B53`. The low byte is still supplied by the ordinary
PPU pointer routine. Every generic mapper transaction invalidates it, including
selector-only inversion changes. Both optimized paths that bypass generic
mapper writes (`bank_switch_enter`, `native_bank_restore`) also invalidate it.
Non-CHR addresses retain the shadow pointer; decimal callers take the original
uncached resolver. The cache's internal contract is the resolved pointer, not
the old resolver's temporary X/scratch/flags. Public callers retain their own
register-saving conventions. No graphics, original sound data or game timers
were changed.

## Executable validation

`python3 -m tools.check_chr_read_cache --core
.deps/snes9x/libretro/snes9x_libretro.so --out <fresh-directory>` builds and
executes both scalar and cached cartridges for all 32 high pages and both
mapper inversion modes: **128 cartridges**. Each runs the actual adapter
suite and all 256 selected CHR-register values, independently checking
bank/quarter-specific ROM sentinels through buffered reads. It includes:

- Repeated reads of the identical address, so the checked byte comes from
  the cache hit as well as from a miss.
- Adjacent-page changes without mapper writes.
- Selector-only inversion without a data-register write.
- Optimized paired-bank entry and restoration with a live cached pointer.
- The existing adapter suite's PPU/bulk/controller/banking checks.

`chr-cache-oracle-448/report.json` passes and rejects six actual ROM mutants:
missing invalidation in each of the three mapper paths, ignored page key,
ignored valid bit and wrong cached pointer-high byte. Ignored validity fails
the initial buffered read in case 2; the other five fail mapping case 13.
All eight runtime copies are patched with exact preimage checks and a repaired
ROM checksum. Reports bind sources, core, tools, ROMs, execution logs, RAM and
positive receipts, and reject source changes during a run.

Failed attempts remain retained. Run 445 used a negative-control state in
which paired-bank entry did not change inversion, so its mutant survived;
446 uses a genuinely changing state. Run 446 then exposed an overly specific
failure-case expectation: the invalid-validity mutant failed earlier at case
2. Run 447 exposed a substantive buffered-read test gap: the wrong cached high
byte survived because the returned sentinel came from the initial miss, while
the incorrect next read landed on indistinguishable filler. Repeating the
same address fixes that coverage gap; fresh full run 448 rejects it. These
earlier runs are not counted as full passes.

The matrix does **not** establish decimal-mode or interrupt-interleaving
equivalence across arbitrary states. It does not compare private cache or
discarded resolver scratch as if they were a public ABI. 454 Python tests pass.

## Integrated evidence

| Check | Result |
| --- | --- |
| Whole loads, rooms 1/2/3 | **23 / 30 / 29 frames**, baseline 24 / 30 / 29; NES 20 / 31 / 30 |
| First scenery after rendering enable | 8 / 7 / 7; NES 7 / 7 / 7 — still fails |
| Fixed fade-offset backgrounds | Room 1 differs only at offset 7; rooms 2/3 match all 40 |
| Adaptive background sweep | **753 positions exact**, coverage 259 / 76 / 143 / 275 |
| Late scroll publications | None in the new sweep |
| Strict settling-time gate | **Fails five samples**; kept failed |
| Present Status | Opening and reopening both zero-pixel difference in tested stats region |
| Scoped stable-park packet cadence | No intervals over 1.5 frames |
| Audio transport | 9,042 completed-NMI packets; no unfinished tail or unflushed writes |

The settling calculation can first see a camera position on the outward pass
and first see it consecutively on the return pass. Its long values are not
automatically literal multi-second freezes. The gate is retained, not relaxed
or presented as a pass. No exact combat-state parity between different ROM
timings is claimed.

Evidence: `chr-cache-entry-440`, `chr-cache-background-audit-444`,
`chr-cache-status-audit-444`, `chr-cache-park-audit-445`,
`chr-cache-audio-445`, `chr-cache-neutral-445`. Full normal and observed replay
timelines/PCM match independently; fixed replay is 9,408 frames and adaptive
replay is 8,803. That total difference is not a whole-game speed ratio.

`chr-cache-load-cost-447` binds the actual rendering-off window, frames
2104..2118, to a full observer-neutral instruction trace. There are still
828 resolver entries, but their own-region elapsed clocks fall from 414,928
to **304,328**, a saving of **110,600** (about 26.7%). Nested helper costs are
separate; no original wait loops or fade counters are removed. Rendering
enable advances from frame 2120 to 2119.

The remaining first-visible delay, full speed/endurance, strict scrolling
acceptance and physical gameplay audio remain open. Transport evidence and
reviewable PCM are not proof of pop-free output. Review page:
`http://127.0.0.1:8766/chr-cache-review-449/`.
