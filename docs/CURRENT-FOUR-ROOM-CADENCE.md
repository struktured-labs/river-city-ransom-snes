# Current ROM: four-room main cadence and background qualification

September18, 2026. No game-code/artwork change, Rival input or restart. The
previous goal turn found ambiguous musical-context candidates for the three
physical gaps; that remains incomplete. This turn returns to speed/scrolling
and closes a current-build background-coverage gap without relaxing its gate.

Review: <http://127.0.0.1:8766/triangle-route-review-980/>.

## Exact-PC complete game iterations

The current port's previously neutral loop capture896 retained non-park loops
but audit897 qualified only stable park iterations. New auditor
`audit_route_loop_cadence.py` examines every stable iteration in rooms0–3, with
the same original RAM predicates on NES and SNES. A fresh original-NES
capture977 records F27D start, F282 input call and F2DA completion through the
whole route. Its8,548-frame timeline and PCM exactly match independent normal331.
The original opcode preimages, trace bounds and every point are validated.

| Room | NES loops | NES three-tick loops | SNES loops | SNES non-two-tick loops |
| --- | ---: | ---: | ---: | ---: |
| School street0 | 594 | 1 | 601 | 0 |
| Alley1 | 1,741 | 12 | 1,742 | 0 |
| Mall2 | 470 | 0 | 476 | 0 |
| Park3 | 729 | 0 | 769 | 0 |

All3,588 stable SNES iterations take exactly two ticks. Consecutive stable
starts have600/1,741/474/768 two-frame intervals by room and no exceptions.
The13 longer NES iterations also produce13 three-frame start intervals. Each
system retains70 excluded non-stable iterations and one censored boundary.
The fixed minimum is64 complete iterations per room; all four exceed it.

NES `$010B` is cleared by the verified original instruction before input and
sampled at completion. SNES uses the existing observed16-bit native NMI counter.
NES reported scanline240 is not treated as an exact physical VBlank position.
Clock units remain separate: NES CPU cycles versus SNES master clocks.

The NES therefore fails an absolute “all loops exactly two ticks” rule on its
own. These natural overruns remain in the report rather than being excluded.
Different encounters preclude calling the port13 loops faster, or treating the
table as equal-work combat speed. Input-to-render latency and whole-game speed
are not certified by iteration counts. Report978 leaves those verdicts false.

Eight tests cover input tick reset, exact stack restoration, missing/duplicate
events, fixed four-room coverage, a retained three-tick failure, irregular
starts despite two-tick completion, pause/transition/room boundaries, and
censored edges. **704 unit tests pass.**

## Current exact background comparison

Window-capable background capture976 is neutral to the full8,934-frame normal891
timeline and PCM. Audit979 reuses original background333/normal331 and the
executed80-case observer oracle338. The original broken-scroll ROM336 remains
a required real negative control and still fails pixels and settling.

All800 common first-stable camera positions match the original at every pixel
in the fixed256×160 background playfield. Primary actor-bearing images are
retained separately. Settling is no later than NES at every selected position.
Common coverage by room is259/103/110/328, all above the unchanged64 minimum.
This closes the room1 coverage deficit seen on the earlier783 build without
changing the route, thresholds or favorable-frame selection.

The combined report deliberately remains **FAIL** because885 eligible
end-of-frame logical/published-scroll comparisons violate the old same-frame
rule. Every other gate passes. These885 observations are not automatically885
visibly late frames: the next audit needs actual store-to-render timing, not
another frame-end RAM comparison. No strict gate was removed or weakened.

The initial974 capture accidentally used the older background core, whose hash
does not match the window-aware oracle. The attempted975 audit correctly
rejected it before generating a report. Capture976 uses the qualified core;
979 is the current result. Neither observer capture changed the game ROM.

Review980 includes unaltered NES/SNES image pairs at fixed nonzero checkpoints
in all four rooms, the full background dashboard, and every loop/exclusion.
Actors differ between encounters; no actor masks or image realignment are used
to hide that. Current live ROM remains071c89e; its state was not touched here.

Next: use a sparse exact-PC store observer joined to rendered scanlines to
extend the old bounded park latency comparison to the current build. This can
distinguish genuine extra presentation latency from an unsuitable frame-end
comparison, while preserving old failures and original NES same-frame cases.
