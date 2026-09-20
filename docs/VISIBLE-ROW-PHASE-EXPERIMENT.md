# Row preparation phase: executed and rejected

This goal turn made progress by testing the next scheduling hypothesis and
finding its actual full-route regression. It is not a speed/scrolling fix.
No Rival restart, hardware input, OBS change, or change to the live ROM.

## Candidate and safety boundary

Candidate670/678 (`90d1b08fc768fc7ffefbb2fea5ecabab0bb817e9d86a9f37245ce0c475c8463e`)
uses default-off `--experimental-visible-row-phase`. It retains parent608's
graphics and sound engine; the attribute cache and line30 experiment are off.
Stable, unpaused gameplay prepares four rows at original tick1 and leaves
rows pending at tick2. All other gameplay keeps its ordinary two-row budget.
Palette/sprite/CHR work and sound still execute every original NMI. Guards
retain old behavior during pauses, fades, other tasks, transitions and other
counter values. No synthetic game tick, speed override or added input delay.

`row-phase-oracle-678` executes300 cartridges covering the guards, both
mirroring modes and six ring/page/quadrant boundary starts. It checks every
staged byte, row flag, original-game RAM byte, shadow byte, VRAM byte and
initial requirement, plus DP/DB/stack, cursor, budget and deferred dirty latch.
Six actual incorrect programs are rejected: wrong first budget, missing defer,
missing pause/transition guards, counter overreach and lost pending work.
The current-source disabled build is byte-identical to parent608. This
experiment's isolated correctness does not certify its publication schedule.

## Full route contradicts promotion

Normal, renderer, background, full span/ACK and bounded instruction captures
complete8501 frames. Each observer's full timeline and PCM match normal.
The shorter route than608 is **not** a speed claim: encounters differ.

| Actual uniform2px camera1/3 pairs | NES | Parent608 | Candidate670 |
| --- | ---: | ---: | ---: |
|Park east|3|11|20|
|Park west|0|18|31|

`row-phase-display-673` retains every measured hold, including long stops.
`row-phase-cadence-677` separately shows camera calculations averaging about
two frames; that average does not certify smooth presentation.

`row-phase-background-audit-675` fails one of682 selected positions: room2,
logical camera229, candidate frame6950. Expanded background differs in6046
pixels. This is a two-pixel camera-position mismatch, **not demonstrated tile
corruption**. Actual renderer lines all show227. Original RAM's camera store
does not become229 until frame6950, line30, cycle672; the early-copy cutoff
is line30 exclusive. Frame6951 displays229. The comparison had selected the
second consecutive logical-camera observation, not a favorable pixel frame.
The fixed two-frame logical-position criterion remains failing; it is not
waived. CPU capture678 and renderer671 both match normal execution;
`row-phase-publication-680` retains the bound actual store instructions.

Strict split/held-camera audits reject missing renderer coverage at frame2120.
The new diagnostic `audit_renderer_failures.py` preserves that failure while
continuing to inspect other complete frames:7186 of7187 eligible frames have
all160 lines; zero splits and zero stale-held-camera failures in the covered
frames. It does not turn missing coverage into a pass. Frame2120 is at the
first room's fade boundary; frame-end PPU/task state alone cannot explain why
no renderer lines were emitted. The complete run is not certified split-free.

Whole room-change-to-visible times are21/29/29 frames versus NES20/31/30;
the first load regresses by one frame versus parent608. Fixed fade comparison
also fails. Present Status first/reopened screens have zero mismatch pixels;
short movement passes21px versus21px, but neither overrides route failures.

## Timing and audio evidence, bounded claims

`row-phase-schedule-679` binds actual helper instructions and results in
frames7400..7465:31 four-row decisions and29 deferred decisions. Original
main-loop entries in that window occur at lines52..66 versus parent trace650's
lines52..88. Different encounters prevent attributing a universal speed ratio.
The full-route stage report677 has zero long stable-park NMI intervals.
The schedule audit validates8353 acknowledged audio packets and finds no
stable-park packet gap longer than1.5 nominal frames. These do **not** prove
absence of clicks or acoustic equivalence. No new audio fix is claimed.

550 Python tests pass. New failure-diagnostic tests reject missing, duplicate
and unsupported lines, retain later stale-camera failures after a coverage
failure, and detect a one-line split. `audit_park_spans` now explicitly accepts
the existing single-sweep scenario as well as park stress, with its original
neutrality, binding and stable-state checks unchanged.

Next investigation must address the variable completion time of camera-bearing
game logic and its publication boundary. Rebalancing row counts alone both
misses that boundary and changes first-load timing; do not promote it or mask
the defect with an extra fixed frame of camera latency.

Review: <http://127.0.0.1:8766/row-phase-review-680/>.
