# Invocation-local attribute cache: faster batches, fade scheduling still open

The opt-in `experimental_hidden_high_cache` removes repeated high-byte
conversion for adjacent rows during hidden loading. It is **not deployed**.
The twelve-row combination improves park loading, but is not a replacement
for candidate 344 yet: room 1 remains late and room 2's later fade steps regress.

## Implementation and ownership

Adjacent pairs of tile rows use the same eight NES attribute bytes and the
same vertical quadrant. `hidden_direct_rows.inc` caches their 32 converted
SNES tile high bytes in the existing `$7E:55A0..55BF` scratch buffer. Its key
is the physical attribute-group address OR the vertical-quadrant bit. The
addresses are eight-byte aligned, so that bit is available without collisions.

The cache is **local to one `native_prepare` invocation**. Entry invalidates
the key at native scratch `$1E20..21`; main code cannot run and change the
shadow or pattern half while the NMI-masked producer is active. A hit skips
only attribute conversion. Both actual VRAM DMA planes, row ownership,
initial requirements, mirrored-row checks and mandatory forced blank remain.
Queued states 2/3 are never overwritten. No original graphics or game-state
counters are edited. The builder requires the existing hidden direct-row path.

The default-off build `hidden-high-cache-off-352` is byte-identical to
candidate 344 (`070fb1dfae9dffe4f897366a6a940f6e5e8b9e73db7e7df0023e9f8e8520b7b6`).
All new cartridge variants remain explicitly experimental.

## Executed oracle and measured saving

`hidden-high-cache-oracle-352` passes **4,096 cartridge cases**: all 128
starting rows, both mirroring modes and pattern halves, budgets 1/2/10/16,
and one or two producer calls. Repeated calls change both the source bytes
and pattern half. The checker compares all 8,192 actual tilemap VRAM bytes,
all ownership/requirement entries, the complete original shadow and immutable
staging against an independent per-tile NES attribute oracle.

Four executed mutants are rejected: missing per-call invalidation, missing
vertical quadrant, missing physical page, and unconditional reuse. A sparse
two-page command case exposes physical-page aliasing. Four uncached controls
also pass. `hidden-high-cache-budget-oracle-360` adds **256 executed cases**
at budgets 12/14, including map/ring boundaries and changed subsequent calls.

`hidden-high-cache-timing-354` compares eight actual ten-row-budget batches
with and without caching. Both arms separately pass the VRAM oracle and
produce identical graphics/ownership; the read-only timing core produces
identical RAM to each normal run. Savings are **12,130–15,626 master clocks**
per tested batch. This is measured producer work, not a whole-game speed ratio.

The initial fixture attempt 350 failed assembly because the new A16 entry
lacked an assembler width directive; no test execution was counted. Corrected
fixture 351 and the full oracle above execute successfully. 428 Python unit
tests pass separately from the cartridge matrix.

## Full-game batch-budget comparison

Every variant below completes the fixed park route and passes its scoped
stable, unpaused packet-delivery gate. **Every variant still fails the full
room-entry timing/fade gate.** Earlier colors are retained as differences,
not excused because the first-visible deadline is met.

| Hidden row budget | First scenery, rooms 1/2/3 | Whole room-change-to-visible | Fade result |
| --- | --- | --- | --- |
| NES reference | 7 / 7 / 7 | 20 / 31 / 30 | Reference |
| Parent 344, uncached 10 | 8 / 7 / 8 | 25 / 30 / 30 | Room 2 exact |
| Cached 10, candidate 352 | 9 / 7 / 8 | 25 / 30 / 30 | Room 1 first color regresses; room 2 later colors lag |
| Cached 12, candidate 356 | 8 / 7 / 7 | 24 / 30 / 29 | Room 3 exact at all 40 offsets; room 2 differs at 11/15/19 |
| Cached 14, candidate 359 | 8 / 7 / 6 | 24 / 30 / 28 | Room 3 first color one frame early; room 2 differs at 11/15/19 |
| Cached 16, candidate 356 | 8 / 6 / 7 | 25 / 29 / 29 | Room 2 first color early; room 3 differs at 11/15 |

Reports are `hidden-high-cache-entry-355`, `hidden-high-cache-12-entry-358`,
`hidden-high-cache-14-entry-361` and `hidden-high-cache-16-entry-358`. No result
is relabeled as a different budget, and no room-specific budget is selected
to fit the reference. The twelve-row version is a useful diagnostic candidate,
not a qualified release.

Candidate hashes:

- Cached 10: `99caa8269d2f2146e4cab6eb0b98c55ae8bb3842e16fc33ddc5b4cbc5f54eb2d`
- Cached 12: `f3a0cc988bc322ed14336af7bde5b0267ee4c2540c7580b8b291a6916421e00b`
- Cached 14: `c60e55147b70d7d26cddee163850fa1a43dc13cf2dda47ac4e0895a81ae95f7a`
- Cached 16: `5e114b0812ccb52065af59463bb283ea9d6ba8cee51b7eea1ff772bf1a414cd9`

## Neutral replay and audio limits

`hidden-high-cache-load-355` verifies the complete 9,406-frame cached-ten
timeline and PCM against the normal core. `hidden-high-cache-12-load-361`
does the same for all 9,408 frames of cached twelve. Their observed hidden
row stages are retained without selecting only the quickest batches.
Normal capture 353 has additional palette telemetry; normal capture 354,
with identical telemetry fields, is the qualified ten-row neutrality control.

The full transport audits `hidden-high-cache-audio-355` and
`hidden-high-cache-12-audio-360` verify respectively **9,033 and 9,034 packets**,
one for every completed NMI, without unfinished tails or unflushed CPU writes.
Full PCM and transition-gap clips are available. Stable park timing passes,
but transition gaps still exist: this is not physical audio, subjective
pop-free playback or complete tempo verification.

The new `hidden-high-cache-profile-356` is bound to cached ten, not the parent.
Its first game-update call has 670,688 elapsed clocks, 422,156 in ordinary
NMIs. Earlier execution changes enemy/game work, so those numbers must not
be subtracted from the parent's profile as an equal-work performance gain.
The paired synthetic timing above is the equal-output saving measurement.

Fresh cached-twelve integration also passes:

- `hidden-high-cache-12-background-audit-363`: **789 common camera positions**
  (rooms 0/1/2/3: 259/72/110/348), exact background pixels in both the original
  strip and expanded y=32..191 playfield, no late scroll publications, and
  adequate unchanged minimum coverage. Both complete 8,553-frame SNES
  observer/normal runs match in all original fields and PCM. The pinned NES
  observer is likewise neutral, the 80-case renderer qualification is
  revalidated, and the real broken-scrolling control is detected again.
  Original composed screenshots remain alongside the independent planes.
- `hidden-high-cache-12-status-audit-363`: both Present Status entries match
  NES with zero pixel differences and correct game-RAM values.

The state-aware scrolling route completes sooner than on the parent, but
enemy behavior and input durations differ. That is not an equal-input
game-speed benchmark or evidence that combat/endurance is finished.

## Next step

The next loading problem is generation/publication phase, not correctness of
the reused row attributes. Cached twelve retires hidden rows sooner and makes
the park fade exact, but room 1 still needs earlier game-generated colors and
room 2 needs the original publication phase. Trace these boundaries before
changing the scheduler; do not patch game fade counters or tune individual
rooms. Full-game combat/endurance, pause integration and physical gameplay
audio acceptance remain open. No Rival restart or controller-mode change.

Reproduce the main oracle and equal-output timing with:

```sh
python3 -m tools.check_hidden_high_cache --core .deps/snes9x/libretro/snes9x_libretro.so --out build/cache-oracle-new --full
python3 -m tools.check_hidden_cache_timing --core .deps/snes9x/libretro/snes9x_libretro.so --observer .deps/snes9x/libretro/rcr_span_ack_libretro.so --out build/cache-timing-new
```
