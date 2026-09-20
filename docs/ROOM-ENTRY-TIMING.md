# Dense scrolling and room-entry timing — experimental, not deployed

Current Rival build remains `765052c`. This investigation extends the scope
beyond that build's passing short movement and park packet-deadline checks.

## Dense camera sweep

`tools/audit_scroll_sweep.py` compares the first second-consecutive eligible
sample at every shared room/camera position. Selection uses original game
RAM, not image similarity. The fixed RGB555 band is x=0..255, y=32..79;
missing positions and every mismatch are retained. Scroll publication is
checked on every eligible SNES frame. This does not compare independently
evolving actor states or establish whole-game speed.

[Initial sweep](../build/oam-word-scroll-sweep-209/index.html): 455 common
positions, 452 exact bands, three entry mismatches and no late scroll-table
publications. Shared-position counts are 259/22/109/65 for rooms 0/1/2/3.
The minimum-64-per-room coverage gate correctly fails in room 1. Do not lower
that minimum or infer that unmatched camera positions are visually correct.
The original checker source is retained with this failed report.

Visual inspection corrected the initial interpretation: the three entry
mismatches compare a black NES frame to an already-visible SNES room, not
corrupted SNES scenery. Game task C0 is not sufficient to identify a visible
frame. The snapshots also do not have equal elapsed time from room entry.

## Direct NES rendering telemetry, proven non-mutating

`tools/libretro_memory.py` reads the exact `PPUREG` descriptor advertised by
the existing FCEUmm core through `RETRO_ENVIRONMENT_SET_MEMORY_MAPS`. Descriptor
layout and address/length come from the local pinned libretro header and core
implementation. No emulated read, memory write, custom core build or cycle
change is involved. `benchmark_capture.py --ppu-telemetry` stores all four
register bytes; the verifier checks the observation schema and source hash.

Fresh original capture `build/park-ppu-nes-210` has all 9,404 original timeline
rows identical after removing only the new register field, and byte-identical
PCM to `build/park-stress-nes-150`.
[Observer-neutrality receipt](../build/park-ppu-nes-210/observer-equivalence.json).

[Rendering-enabled sweep](../build/oam-word-visible-scroll-sweep-210/index.html)
still fails at the three entry samples. Actual PPUMASK is now enabled there,
but the original palette fade is still black. This second failure is retained;
render enable alone is not proof that the original fade has finished.

A real old broken-scrolling ROM is replayed as a negative control, not just a
missing-data failure: [negative sweep](../build/scroll-negative-sweep-211/index.html)
catches **881 late publications and 22 differing bands** over 412 shared
positions. Its room coverage passes. Thus the late-publication rejection is
independent of the newest candidate's incomplete alley coverage.

## Actual loading delay

`tools/audit_room_entry.py` anchors on the first actual rendering-enable edge
in each of rooms 1, 2 and 3, then compares 40 fixed frame offsets. It retains
every band mismatch, brightness trace, original palette shadow and source
hash. First nonblack band pixels measure visibility latency; they are not
used to shift or select matching frames. Original palette-copy disassembly
at E477 confirms the shadow source is `$0110..$012F`.

| Candidate | Room 1 first visible | Room 2 | Room 3 | Late stable park packets |
| --- | ---: | ---: | ---: | ---: |
| Original NES | 7 | 7 | 7 | not an SPC transport |
| Live 765052c | 29 | 29 | 30 | 0 |
| Hidden rows 4 | not separately audited | — | — | 2 |
| Hidden rows 8 | 12 | 11 | 11 | 0 |
| Hidden rows 16 | 12 | 11 | 12 | 0 |
| Hidden rows 8 + full hidden scan | 12 | 11 | 11 | 1 |

Offsets are display frames after each system's own rendering request, not
absolute boot frames or a combat-speed ratio. All room-entry/fade audits
remain **FAIL** against the original seven-frame visibility target and strict
fixed-offset pixel equality:
[live](../build/room-entry-live-audit-214/index.html),
[eight](../build/room-entry-hidden8-audit-214/index.html),
[sixteen](../build/room-entry-hidden16-audit-216/index.html),
[eight + scan](../build/room-entry-hidden8-scan-audit-217/index.html).

The live port's extra initial-publication barrier hides the original palette
fade while prepared graphics drain. Original game task C0 selects a two-row
producer budget even during this hidden state. The new opt-in
`--experimental-hidden-rows N` changes that budget **only for transition
state 2 under task C0**. State 0 gameplay, state 1 rendering-off work and menu
budgets remain unchanged; the 2,048-byte DMA limit is untouched. The default
is unset. A default-off rebuild (`build/hidden-rows-None-212`) is byte-identical
to the unbranded gameplay parent 200.

Increasing to sixteen does not improve first visibility. In its room-2 load,
frames 5658/5659, 5660/5661 and 5662/5663 have identical consecutive NMI
counters: producer work is causing missed load-time interrupts. The passing
stable-park packet gate excludes loading and must not conceal this failure.
The existing full hidden-ring scan also fails to improve visibility and
reintroduces one stable-park deadline miss. Neither variant is advancing.

## Eight-row candidate and executed regressions

ROM `build/hidden-rows-8-212/native-cpu.sfc` SHA-256:
`5e58a6fb21f96c3ac33e87a647c719453c57e8f0eef16170f591d7b5ade1d172`.
It has **not been branded, deployed or hardware-audited**.

- [72-case hidden-row oracle](../build/hidden-rows-oracle-216/report.json):
  budgets 4/8/16, states 0/1/2, both pattern halves, both mirroring modes and
  menu/game tasks. Every case checks the exact first-batch flags/budget and
  all 3,840 visible tile words. A budget leaking into visible gameplay and a
  wrong hidden budget are both rejected after real emulation.
- [Park packets](../build/hidden-rows-8-park-audit-213/index.html) pass, with
  [observer-neutral timeline and audio](../build/hidden-rows-8-spans-audit-215/index.html)
  across all 9,409 frames. No long NMI-entry intervals in the profiled window.
- [Movement](../build/hidden-rows-8-movement-audit-214/index.html),
  [status](../build/hidden-rows-8-status-audit-214/index.html),
  [repeat purchases](../build/hidden-rows-8-repeat-audit-215/index.html), and
  [YES/NO with old stale-cursor control](../build/hidden-rows-8-no-audit-215/index.html)
  pass.
- All [nine fixed pause checkpoints](../build/hidden-rows-8-pause-audit-215/index.html)
  now pass. However, the [every-frame animation audit](../build/hidden-rows-8-pause-motion-216/index.html)
  remains failed at offsets 2, 3 and 4, just like the older gameplay parent.
  Permanent blank occurs at offset 49, matching NES; this is not full animation
  parity and not evidence that the hidden budget directly fixes pause logic.

Python suite: **351 tests pass**. No Rival restart, OBS setting change or
hardware audio-fidelity claim in this investigation. Next work is the remaining
initial-publication latency/fade fidelity and explicit alley sweep coverage,
without sacrificing interrupt/audio cadence or weakening the original gates.
