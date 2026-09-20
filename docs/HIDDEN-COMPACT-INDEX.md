# Compact hidden-row indices: verified saving, alley visibility still late

Experimental cartridge `hidden-index-1386`, SHA-256
`c83ebaa82b88859fdadb8af16cc428a7cf503360475cc22db892841c6a871123`.
Rival remains on `fa882cb61138`. No restart, inputs or OBS changes.
Review: <http://127.0.0.1:8766/hidden-index-review-1401/>.

## Change and exact patch boundary

Default-off `EXPERIMENTAL_HIDDEN_COMPACT_INDEX` keeps the attribute index in
Y instead of reloading/incrementing its direct-page copy eight times. It
restores the old final Y and index. A 128-byte lookup includes both pattern
halves, replacing two per-pair selector ORs with one per-group index OR.
Attribute quadrant selection, invocation-local cache, forced blank, direct
DMA, mirrored row ownership and requirement retirement remain unchanged.
Original tiles, game counters, fade logic, visible conversion and SPC are
not edited. The private `$08` scratch value now holds the table-index bit.

The complete helper is 779 bytes instead of 792. `build_hidden_index_trial`
first assembles the disabled helper and requires exact equality to the live
cartridge's 792-byte region. The enabled body is assembled at the same entry
and padded within that region. No outside labels or call sites move.
`hidden-index-patch-1394` verifies all 720 differing ROM bytes are confined
to this helper/checksum, validates checksum and complement, preserves every
outside symbol record, and reassembles at the oracle's linked address to
prove byte equality with the executed fixture. Duplicate scoped ca65 labels
are compared as records, not incorrectly collapsed into a name dictionary.

## Executed correctness and timing

`hidden-index-oracle-1389`: **6,144 cases**, every starting row, both mirror
and pattern-half modes, budgets 1/2/16, one or two calls with changed source
and pattern data, and mixed/all-dirty aliases. The independent oracle checks
all 8,192 actual VRAM bytes, source and immutable staging, all row flags and
requirements, cursor and both budgets. Five actual bad variants are rejected:
wrong pattern index, wrong quadrant, missing index advance, wrong pattern
table and stale invocation cache.

`hidden-index-timing-1387`: eight ten-row batches with equal delivered VRAM
and ownership save **3,930–4,780 master clocks**. Both arms pass the independent
oracle, and their observed full RAM matches their respective normal runs.
This is an equal-output helper timing measurement, not a game-speed ratio.

`hidden-index-instructions-1395` is neutral over the complete 8,861-frame
normal1388 timeline and PCM. `hidden-index-phases-1396` compares state-selected
alley work with parent1384: the first three hidden row phases each shrink by
7,130 clocks. Later interrupt work can grow as scheduling changes. The first
main-start-to-fade interval improves only 6,250 clocks, from 1,012,156 to
1,005,906, and does not cross the display deadline. These elapsed measurements
include DMA/events; enclosing and nested costs must not be summed.

## Full-game outcomes retained, including failures

| Candidate | First visible offsets, alley/mall/park | Room-change-to-visible | Fade failure |
| --- | --- | --- | --- |
| NES | 7 / 7 / 7 | 20 / 31 / 30 | Reference |
| Current16 | 8 / 7 / 7 | 22 / 28 / 29 | Alley 7/11/15/19 |
| Compact16 | 8 / 7 / 7 | 22 / 28 / 29 | Alley 7/11/15/19 |
| Compact12 | 8 / 7 / 7 | 21 / 28 / 29 | Alley 7 |

Reports1390/1393 compare all forty fixed offsets and keep rendering-off and
room-change anchors separately. Both candidates fail overall entry acceptance.
Compact12 (`hidden-index12-1391`, SHA `4187cbd211df38106656b5bb9bef0208f1e7e5d77d95e8ff74933a5f4cecc4a5`)
is the same helper plus the guarded budget-byte experiment. It does not inherit
Compact16's separate cadence/renderer qualification.

Compact16's fresh main/render captures1397/1398 are neutral to normal1388.
Cadence1399 passes all 3,550 sampled stable loops, each two NMI ticks, with
two-frame consecutive stable starts. The park has no short irregular holds.
Renderer1400 reports no missing coverage, split scrolling or stale-camera
failures. This does not establish tile-content or physical/full-game speed
equivalence. No new acoustic fidelity certification is claimed.

Normal parent/current runs have equal frame counts and delivered inputs, but
81 video frames and 5,371 sampled game-RAM frames differ; full PCM also differs.
The web review records every differing frame. Same-duration routes must not
be advertised as whole-route output equivalence or equal-work performance.

856 Python tests pass. A new checksum-corruption test caught a verifier gap:
checking only the sum can accept a self-consistent checksum-byte mutation;
the patch auditor now requires its complement too. Earlier failed checker
attempts produced no passing receipt and are not counted as qualification.

## Reproduction and remaining work

```sh
python3 -m tools.build_hidden_index_trial --parent build/postpublish-keyon-1321 --out build/new-index
python3 -m tools.check_hidden_compact_index --core .deps/snes9x/libretro/snes9x_libretro.so --full --out build/new-index-oracle
python3 -m tools.check_hidden_cache_timing --core .deps/snes9x/libretro/snes9x_libretro.so --observer .deps/snes9x/libretro/rcr_span_ack_libretro.so --compact-index --out build/new-index-timing
```

No candidate is promoted. The next timing change must address the remaining
game/update/publication schedule, not edit original fade counters or relax
the first-visible deadline. Physical audio gaps, the older hardware camera
hold and full-game original-speed acceptance remain open.
