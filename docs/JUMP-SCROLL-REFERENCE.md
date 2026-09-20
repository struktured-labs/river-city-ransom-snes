# Jumping and the physical camera holds

September 18, 2026. No game ROM changes or Rival/OBS operations in this iteration.
Current tested candidate remains `0956bd97b78f`.

- [Matched NES/SNES episode and untouched frame sequences](http://127.0.0.1:8766/jump-scroll-review-1318/)
- [Rival hold context: fifteen original decoded pictures](http://127.0.0.1:8766/physical-hold-review-1319/)

## A stronger comparison, not a speed waiver

`capture_jump_scroll.py` runs the same logical NES controls on both systems:
960 frames right, then 240 left, with A+B held 18 of each 30 frames. Direction
remains held during jump release. There are 60 idle and 60 settling frames.
This approximates the requested physical input schedule, not its exact input
consumption, initial state or enemy encounter. No save states or memory writes.
The wrapper registers its scenario only inside its own process and separately
binds its source; historical benchmark helper hashes are unchanged.

Captures1316/1317 complete in 2,332/2,642 frames, respectively, including their
different startup durations. Total capture length is not a gameplay speed ratio.
Each retains all 1,320 episode frames, full game RAM, native PNGs and audio.

Audit1318 records player world X, working camera and committed camera on every
episode frame. A separate pixel matcher measures the fixed school-roof strip
(8,32)..(248,56), without scaling or image alignment. All ineligible frames,
ambiguous pairs, room boundaries and long stops remain in the report.

During rightward movement:

| Observation | Original NES | SNES candidate |
| --- | --- | --- |
| Equal-step committed-camera intervals | 183×2, 6×14, 1×3, 2×10 frames | 242×2, 5×14 frames |
| Equal-step scenery intervals | 173×2, 6×14, 6×3, 5×1, 1×9, 1×11 | 242×2, 5×14 |
| Short scenery irregularities (1/3/4 frames) | 11 | 0 |

The original player's world X changes at frames1543 and1546, its committed
camera at1544 and1547, and scenery at1545 and1548: a three-frame movement gap
exists on the original too. Other original one/three-frame picture intervals
need not appear in frame-end committed-camera snapshots. Similarly, the SNES
player-X writes sometimes straddle frame boundaries while its camera and
scenery still advance every two frames. Neither RAM differences nor picture
holds alone prove a complete game-loop slowdown.

Encounters diverge: NES remains in room0 throughout the rightward phase, while
SNES reaches room1 for its last53 frames. During leftward movement SNES has106
room1 frames and134 room0 frames, but no measured camera movement in the
qualified roof strip. This is explicitly **not leftward-scrolling coverage**,
equal-work speed certification, or a reproduction of Rival's four-frame hold.

## Physical evidence narrowed

Audit1319 authenticates the prior camera report and video, then extracts
frames658..663 and1061..1069 directly. The entire recording has1,791 pictures
with1,193 timestamp intervals of17ms and597 of16ms. Both suspect holds have
continuous timestamps; this does not rule out duplicated or dropped pictures
upstream of the encoder.

At frame1065, the fixed actor region changes10,790 pixels by at least32 levels
in one RGB channel; the roof region changes zero at that threshold. This
quantifies the visible enemy motion during the four-frame scenery hold.
Consequently the interval is not an identical whole picture. It still does
not distinguish a game-directed player stop from a delayed background update.
The threshold is descriptive, not a visual-quality gate.

## Regression and remaining work

New tests cover identical logical jump inputs, bounded phase lengths, scenario
registration cleanup, inserted duplicate frames, retained long stops, room/gap
boundaries, rejected picture matches and signed region-difference arithmetic.
Existing historical speed gates have not been weakened.

The physical four-frame hold and short audio pops remain unresolved. Next
use a reproducible encounter/state to connect physical player movement with
camera publication, and keep short-transient audio qualification separate
from previously passed broad-silence checks. Rival was not restarted for
this test-harness-only change.
