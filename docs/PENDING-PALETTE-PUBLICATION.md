# Pending palette publication — room 2 now matches the full NES fade

Latest candidate: `build/pending-palette-queue-327/native-cpu.sfc`, SHA-256
`4339df2e5613e0d5af4ec7aa7e3888b991311281988b75a838f992e9e6d3a958`.
**Not deployed.** Room 2 passes all 40 fixed-offset scenery/fade checkpoints,
but rooms 1/3, dense park coverage and full gameplay/audio acceptance remain open.

## Implementation and ordering constraints

`experimental_pending_palette` adds a native routine at `$C0:7000`, in the
previously unused low half of the bootstrap ROM bank. It has a fixed linker
assertion and a bounded 4-KiB segment; no graphics or sound assets are replaced.
The ordinary publisher calls it only after its existing final-batch beam
check, immediately before OAM/CGRAM upload. Default-off control 317 is
byte-identical to palette-copy candidate 311.

The routine prepares the completed original palette for that upload without
changing original RAM, NES PPU shadow, source cache, PPU write counters or
the original dirty flag. The original NMI still performs its palette copy.
It preserves native caller registers/flags/stack and marks only the prepared
palette generation as needing upload. RGB555 conversion uses the same ROM
lookup, universal background color and transparent-sprite alias behavior.

It requires an initialized pipeline, exactly one NMI level, no paired-bank
critical section, gameplay task, an unguarded original NMI, and `$003E` bits
1 and 3 set. It excludes a pending retained interrupt and a visible iteration
that will retain this NMI. Most importantly, **the original command queue must
be empty**: C50B runs before E461, and its read commands can write zero-page
destinations, including fade eligibility. Predicting through that queue is
not justified. The builder requires the tested deferred scheduler, palette
copy and FastROM publisher, and rejects the game-first experiment.

This is an explicitly limited early preparation path. Nonempty queues still
need a correct ordering solution; declining their preview is not full parity.
Original fade counters have not been patched to force a timing pass.

## Executed evidence for the latest candidate

| Directory under `build/` | Result and scope |
| --- | --- |
| `pending-palette-queue-oracle-327` | 55 asset-free cases: all source byte ranges, eligibility states, empty/nonempty/wrapped queue pointers, native caller ABI, prepared colors, unchanged original/shadow/cache and real CGRAM. Six executed mutants rejected. |
| `pending-palette-queue-entry-329` | First scenery **9/7/9** versus NES 7/7/7. Whole room-change-to-visible **26/30/31** versus 20/31/30. Room 2 has **zero differing pixels at every one of the 40 fixed offsets**. Overall timing/fade gate remains **FAIL**. |
| `pending-palette-queue-park-audit-329` | Zero stable park packet intervals over 1.5 frames; no native faults. |
| `pending-palette-queue-audio-329` | 9,236 acknowledged packets, exactly one per completed NMI; zero unfinished tail, byte mismatches or unflushed writes. Full PCM and transition-gap clips retained; not a perceptual or physical no-pop verdict. |
| `pending-palette-queue-source-329` | Full 9,410-frame timeline and PCM match normal replay. The one preview in the observed room-2 window is followed by the original palette copy before the next NMI. All 25 distinct game-source bytes used for displayed colors match that copy. |
| `pending-palette-queue-scroll-329` | 473 common post-fade positions, zero scenery-band mismatches and late publications. **Coverage FAIL**: 259/83/110/21 positions versus minimum 64 in every room. |
| `pending-palette-queue-status-audit-329` | Both Present Status entries match NES with zero mismatching pixels. |

The CGRAM oracle starts with known hardware colors. Eligible calls entering
the real publisher at lines 240/242 finish at 253/255; late entries at 245/260
leave the buffers/hardware colors alone. Mutants cover the universal color,
unused transparent shadow slots, dirty eligibility, retained-iteration guard,
actual CGRAM destination port and command-queue guard. The initial fixture
could not assemble line 260 as an eight-bit constant; the corrected fixture
checks both beam bytes. The failed run is not counted as validation.

The source correlation audit checks actual ROM instructions, source addresses,
values and same-NMI copy completion. Its full parent comparison retains one
palette-source difference at frame 5665 and two fade-counter differences at
889/8135; there is no claim that all original game RAM is identical. Fade flags
are identical throughout. The observed preview itself uses the same completed
source as the subsequent original copy, not an unfinished generation.

412 Python unit tests pass, separate from executed cartridge tests.

## Superseded prototype and scrolling-audit correction

Prototype 317 lacked the command-queue guard. It reached 8/7/8 first scenery
and passed scoped packet timing, but is **not advancing** because its NMI
eligibility prediction could be invalidated by a queued read command. Its
artifacts remain (`pending-palette-entry-audit-320`, source audit 326 and
oracle 320). Do not attribute its 8/7/8 timing to the safer latest candidate.

The legacy dense sweep selected the first stable camera position during
fading. At room 2/camera 0 it compared a black NES frame to visible SNES
scenery: 9,301 differing pixels. Earlier black-versus-black comparisons were
also not evidence of correct scenery. A first post-fade version then exposed
another problem: a transient boot task could resemble gameplay. Both failed
reports are retained in `pending-palette-scroll-audit-320` and
`pending-palette-post-fade-scroll-322`.

The separate `--post-fade` sweep now starts only after the capture's verified
street arrival and requires the original fade-in completion state: `$003E`
bit 1 clear and `$0692 == 4`. It selects by game state, never by image quality.
Scroll publication checks still cover fading frames. The fixed scenery band,
minimum coverage and separate fixed-offset room/fade audit are unchanged.
The legacy selection remains available and its old failures are not overwritten.

Both parent 311 and prototype 317 then have zero post-fade scenery mismatches
(`palette-copy-gameplay-scroll-323`, `pending-palette-gameplay-scroll-323`).
Crucially, the real broken-scrolling control is still rejected:
`post-fade-scroll-negative-324` has **19 differing bands and 881 late
publications**, despite adequate per-room coverage. Unit tests cover fade
state, transient boot exclusion and retention of fading publication failures.

## Remaining work

Rooms 1/3 still need original generation/publication timing and faster whole
loads. The park route needs adequate verified in-room camera coverage; no
threshold was lowered. Exact-candidate café/pause/movement integration,
full-game speed and physical gameplay audio remain incomplete. No Rival
restart or controller-preset change occurred in this work.
