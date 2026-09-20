# Cached-row palette phase: room 2 corrected, first-room generation still late

Candidate `build/cache-all-level-on-365/native-cpu.sfc`, SHA-256
`84a48c63c1966ed0609bb107bee220b3ca2f81d4bd739e60f46987dd1c613074`.
**Experimental, not deployed.** This builds on cached twelve-row candidate
356, restores room 2's exact fade, and leaves the remaining failures visible.

## Diagnosis and change

The original game generates room 2's four completed, dirty palettes at
offsets 6/10/14/18 after rendering-enable. Cached twelve does the same; the
missing frame was publication delay, not late generation.
`cache12-room2-decisions-367` records the actual linked preview calls:
level zero converts, while levels 1/2/3 return after the initial-level guard.
Those rejected calls enter at scanline 243 on frames 5667/5671/5675.

The new default-off `experimental_pending_palette_all_levels` option removes
only that level restriction. It requires the safe write-head classifier:
READ heads, invalid pointers, retained/reentrant interrupts and late beam
positions remain rejected. The original consumer's one-WRITE fade budget
still supplies the ordering guarantee. No original fade counters, palette
bytes or room-specific rules are changed. The disabled build is byte-identical
to cached-twelve parent `f3a0cc9...`.

`cache-all-level-decisions-367` shows all four room-2 generations admitted;
the later queue controls are WRITE markers 4 at indexes 42/63/20. The
independent `cache-all-level-source-367` checks all four against the original
complete palette copy in the **same hardware NMI**, including all 25 distinct
visible-color source bytes. The complete 9,408-frame observed timeline and PCM
match normal-core replay. Parent differences remain in the report: nine
palette-source, nineteen fade-flag and nineteen fade-counter snapshots. This
is not a claim that all original game RAM remains identical across variants.

## Exact result and limits

`cache-all-level-entry-367` retains all forty offsets per room:

| Room | NES first scenery | Candidate first scenery | Whole load: NES / candidate | Differing fade offsets |
| --- | ---: | ---: | --- | --- |
| 1 | 7 | 8 | 20 / 24 | 7, 11, 15, 19, 20 |
| 2 | 7 | 7 | 31 / 30 | None |
| 3 | 7 | 7 | 30 / 29 | 10, 14 (candidate colors early) |

Room 2's regression is fixed, not simply shifted to an aligned screenshot.
The park's initial visibility remains on time, but two later colors now
appear early. The strict combined loading/fade gate therefore still fails.

Frame-end completed-generation observations explain why one universal preview
rule cannot itself fix all phases. NES uses 6/10/14/18 in all three rooms.
Both cached-twelve variants generate at 7/11/15/20 in room 1, 6/10/14/18 in
room 2, and 5/9/13/17 in room 3. The final park palette repeats the prior
background RGB values, so its publication is not distinguishable from pixels
alone. No gate is relaxed for that ambiguity.

## Verification

- `cache-all-level-oracle-365`: 343 executed CGRAM/ABI/source cases, four
  rejected mutants, with all-level admission enabled.
- `cache-initial-level-oracle-366`: 343 cases/four mutants recheck the unchanged
  default initial-only policy. 429 Python unit tests pass separately.
- `cache-all-level-background-audit-369`: fresh exact-candidate background
  comparison passes all **789** common positions, including **348** in the
  park. Both playfield regions match; no late publications, sufficient
  per-room coverage, full normal/observer neutrality, revalidated renderer
  qualification, and a detected real broken-scrolling control.
- `cache-all-level-status-audit-369`: both Present Status entries match NES
  with zero pixel differences and correct numeric values.
- `cache-all-level-park-audit-367`: zero over-limit stable unpaused park packet
  intervals, no native faults. The fixed route is not an endurance proof.
- `cache-all-level-audio-367`: all **9,034** completed-NMI packets verified,
  no unfinished tail or unflushed writes; full PCM and transition-gap clips
  retained. Physical gameplay audio and subjective pop-free fidelity remain
  unverified.

## Next measured speed target

`cache-all-level-room1-profile-369` is bound to this exact candidate and a
complete neutral replay. The first game-update call takes 676,376 clocks,
including 435,048 inside ordinary NMIs. Later in that same iteration, FADA
takes 246,918 clocks but only 2,620 outside its 244,298-clock interrupt.
The call begins at frame 2124, scanline 238, shortly before NMI, and the first
fade service does not run until frame 2125, line 160. That service initializes
fading; it is not the first visible palette.

Reducing earlier work enough to finish this iteration before the interrupt
is the next measured target. There are no CF04 producer entries in this first
iteration, so enabling that unrelated optimization is not supported by this
trace. Preserve original game ordering; do not delay individual rooms or
patch fade counters to fit reference frames. Full-game speed, combat/endurance,
pause integration and physical audio acceptance remain open. No Rival restart.
