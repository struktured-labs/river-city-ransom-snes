# The remaining settling failure samples an unfinished camera calculation

The current candidate is still paired-read build 451, SHA
`71407e8833617f240f0f82190764c248989daa8a6bd81a4322594dd9d1497c73`.
No new ROM is deployed and Rival is not restarted. Full speed, endurance and
physical/acoustic audio acceptance remain open.

## Fixed-frame diagnosis, not a changed gate

`chr-pair-background-audit-458` has one strict settling failure: room 2,
camera 252, NES settle 1 versus SNES 1,259 frames. Its 849 background samples
match and no late publication is recorded. The settling clock starts at the
first eligible `$DC/$DD` working-camera value, then ends at the first time
that same value appears in consecutive frames. Those are different moments
from committing a finished camera position.

Fresh independent captures `chr-pair-transient-{raster,cpu}-463` reproduce the
complete 8,555-frame normal timeline and PCM exactly. The diagnosis keeps
the original selected frames, without searching for better pictures:

| Frame | Phase | Working `$DC/$DD` | Committed / published | Actual renderer, lines 32–191 |
| --- | --- | ---: | ---: | ---: |
| 5719 | enter_alley | 0 | 0 | 0 throughout |
| 5720 | enter_alley | **252** | 0 | **0 throughout** |
| 5721 | enter_alley | 0 | 0 | 0 throughout |
| 6979 | park_entry | 252 | 252 | 252 throughout |

At frame 5720, line 239/cycle 1358, original instruction `C7:E146 STA $DC`
stores low byte `$FC`. An interrupt runs before the next original instruction
`C7:E148 LDA $DD`, which resumes at frame 5721, line 64/cycle 1148. The trace
and pinned cartridge bytes show an interrupted multi-instruction working
camera calculation, not a request to display camera 252. The rendering and
committed state correctly retain camera 0. On the later actual visit to 252,
all observed renderer lines show 252. Thus the 1,259-frame number is **not
a 1,259-frame rendering delay**.

`tools/audit_camera_transient.py` binds the original failed report, normal,
background, renderer and CPU captures, candidate ROM and source code. It
requires all 160 playfield lines and the actual interrupted store/resume.
The original sweep remains failed in both the report and its web page; this
is a diagnosis of one measurement, not whole-game scrolling acceptance.
Tests reject a single-line rendered glitch, a delayed committed publication,
or missing renderer coverage. **459 Python tests pass.** The first wrapper
run 465 rejected an off-by-one preimage slice; corrected run 466 pins the
full literal byte sequence and is the authoritative result.

Evidence and unchanged four-frame collage:
`http://127.0.0.1:8766/camera-transient-audit-466/`.

## Remaining load cost and a rejected scalar-fill alternative

`chr-pair-first-cost-463` profiles the first actual main-loop iteration after
room-1 rendering enable. It starts frame 2119, line 153/cycle 1134 and reaches
the fade service at frame 2121, line 184/cycle 980. The actor update takes
611,764 clocks, of which 374,572 are ordinary NMIs and 237,192 are outside
them. The initial sprite-list call takes 76,752 clocks. A fade-service call
is not necessarily a new palette generation or first visible pixel.

The bound stage trace `chr-pair-first-461-spans.csv` shows hidden row stages
of 87,890 / 88,280 / 87,850 clocks in frames 2119–2121. Sprite conversion in
those stages is only 306–346 clocks: skipping invisible sprites is not the
important target in this measured window. Background work and main-thread
time compete while the initial scene is still hidden.

Disabling rectangle block fills in `chr-pair-scalar-rect-462` (SHA
`f55f3aa03b0f6e38d38d2487edaab27996f7271c3a468d0d4e30b737bc3fc3d8`) completes
the fixed route but does not improve the load: `scalar-rect-entry-464` still
reports 22 / 30 / 29 whole-load frames and 8 / 7 / 7 first-visible offsets.
It is not promoted and has not inherited the paired-read candidate's other
qualification. The comparison baseline remains unchanged.
