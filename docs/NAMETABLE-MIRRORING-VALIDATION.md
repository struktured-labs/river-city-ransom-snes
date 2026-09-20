# Open nametable mirroring gate

## Coordinated candidate (not deployed)

`build/nametable-01` now maps CPU accesses and palette refill through two
physical tables at `$2000/$2400`, dirties both logical aliases, and converts
logical display rows from the selected physical table. Changed `$A000`
mirroring invalidates staged rows; `$A001` is no longer misinterpreted as a
mirroring write. Bulk page/ring operations use the same pointer. Palette
page-fill masking remains a separate open semantic issue.

`build/nametable-positive-01` passes both CPU alias cases. The row oracle now
checks both mirroring modes, both pattern halves and both producer budgets;
all 3840 displayed tiles match in each combination. Distinct unused shadow
tables act as poison against accidentally retaining four independent tables.
The existing graphics and adapter suites pass, as do 86 unit tests (including
the branding agent's new tests). Bulk fixtures now inspect physical storage
and last-write alias semantics instead of requiring nonexistent extra CIRAM.

`build/nametable-quality-01/snes` completes in 2101 frames versus 2039 for
the preceding candidate. This regression is not accepted as original-speed
performance. Alias-driven duplicate row conversion/publication is a target
for optimization, with mirroring correctness retained. Dynamic mapper-mode
changes, attribute alias dirtiness and disabled-mapping mutation controls
still need expanded executed coverage; current CPU gate alone is not full
mirroring certification.

## Original failing evidence

### Pointer simplification and dynamic coverage

`build/pointer-fast-01` initializes the shadow bank once, tail-branches into
nametable mapping, and maps vertical-mode high addresses with `AND #$27`.
The adapter suite passes, but the baseline remains 2099 frames: no measured
whole-script speed gain. Do not substitute an instruction-count argument
for the still-failing original-speed gates.

`build/pointer-fast-nametable-03` passes both modes and automated wrong-mask/
wrong-shift controls. The fixture now changes mirroring without rewriting
physical data, checks both logical layouts afterward, requires all staged
rows invalidated, and verifies an `$A001` write cannot change mirroring.
Its CPU read oracle still uses one tile offset; full attribute/dynamic pixel
coverage remains separate work.

### Shared-row conversion experiment

`build/alias-copy-01` converts each dirty physical row once, then copies its
64-byte completed staging image into the other logical alias only when that
alias is dirty and unqueued (state 1). States 2/3 remain immutable. Producer
budgets still bound full conversions to 2/4, with at most one bounded 64-byte
copy per conversion; first batches can therefore stage 4/8 logical rows.
The expanded row oracle verifies all output bytes in both mirroring modes.
Executed graphics case 11 verifies queued/stale aliases stay untouched and
the first/last words of the eligible alias are copied. Negative controls
remove the queue guard or truncate the block copy and require case 11 failure.

The baseline completes in 2099 frames, just two fewer than the first mirrored
candidate. Settings and initial street pixel gates pass, all four transition
speed gates still fail. This small improvement does not recover the prior
2039-frame run; duplicated conversion is not established as the principal
cost. Per-write mapping and dirty tracking remain optimization targets. The
claim that mirroring is necessary is independent of this performance result.

`tools/check_nametable.py` builds asset-free cartridges using the production
adapter. Each selects MMC3 mirroring through `$A000`, writes distinct bytes
to `$2015/$2415/$2815/$2C15`, then uses buffered PPUDATA reads to check the
last-write alias results. Vertical mode expects `[A2,A3,A2,A3]`; horizontal
expects `[A1,A1,A3,A3]`. These correspond to the two physical nametables,
not four independent logical backing stores.

```sh
python3 tools/check_nametable.py \
  --core /tmp/rcr-snes9x/libretro/snes9x_libretro.so \
  --out build/nametable-gap-02
```

Current result: **fails**, at executed cases 22 and 23 respectively. The
report binds ROM and emulator hashes and keeps full failure logs. This is
an open fidelity gate, not a passing expected-failure test. Existing adapter
regressions remain separately runnable. The initial fixture tests one tile
offset and static modes; attribute bytes, dynamic changes and renderer
behavior need additional coverage before claiming completion.

Code inspection matches the failure: `mirror_write` records `$1C18`, but
the current pointer, row producer and renderer do not consult it. The pinned
FCEUmm MMC3 `GENMIRPW` uses `setmirror((V & 1) ^ 1)`.

Required coordinated correction:

- CPU read/write address mapping into two persistent physical 1KiB tables,
  including `$3000` mirrors and palette-read refill underneath `$3Fxx`.
- Dirty tracking for both logical aliases, preserving staged-row semantics.
- Logical display-row conversion from the selected physical table, including
  attributes and mirroring changes without losing physical table contents.
- Bulk page fill and ring paths, which must not bypass the same mapping.
- Executed positive and mutation tests for both modes, then original-game
  pixel, transition-speed, scrolling and audio regression captures.

All saved phase-end RAM snapshots in `build/palette-buffer-quality-01/snes`
and `build/upper-lane-01/snes` have `$1C18 = 0`; this is sampled vertical-mode
evidence only, not proof no transient changes occur. The user's shop scene
has not been reproduced, so do not label this its confirmed cause.
