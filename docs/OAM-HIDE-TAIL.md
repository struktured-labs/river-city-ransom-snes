# Unused-sprite hiding: measured speedup, return fade still fails

[Timing, NES/trial collages, unprocessed audio and hashes](http://127.0.0.1:8766/oam-hide-tail-review-2195/)
· [Forward room-entry comparison](http://127.0.0.1:8766/oam-hide-tail-entry-2194/)

Offline candidate2186 SHA256:
`eda5323c86af3d4012c534cebf765604cb27e82e7ee3d9aa4d707971ef70bea1`.
No Rival, controller or OBS changes. The splash-only2089 deployment is untouched.
This is progress on CPU overhead, not a release or a fix for physical audio pops.

## Diagnosis and implementation

Completed normal2184 and instruction2185 captures authenticate all2,872 frames
of the one-pass early-preparation candidate2172. All existing timeline fields
and native PCM agree. Its original game creates the four completed, dirty
fade palettes at enable+7/11/15/19, versus NES+6/10/14/18. Thus generation is
already late; changing palette DMA alone cannot recover the missing frame.

The first post-return game iteration spends7,038 elapsed master clocks inside
DFE2, hiding unused sprites. Original code writes Y=$F0 at descending aligned
OAM offsets, repeatedly decrementing X four times and testing the loop.
`snes/oam_hide_tail.asm` dispatches to the equivalent fall-through sequence of
absolute stores. It retains the original zero-cursor return and final A/X/P,
uses no scratch RAM, and leaves register widths and interrupt enable unchanged.
Unaligned cursor values retain the original (nonterminating) loop.

The guarded builder replaces only the three-byte entry at C1..C8:DFE2,
places the helper/table in previously FF-filled C1..C8:7C00–7EFF, and updates
the checksum. Existing original fallback/return code, early-preparation helper,
signed-shift helper, game data, graphics, timers and SPC remain unchanged.
This is a separate default-off derived candidate, not a change to the default build.

## Executed correctness and timing

Oracle2189 executes131,072 cases: all64 terminating aligned OAM cursor values
times all256 supplied status bytes in each of eight program/data-bank pairs.
E=1 forces M/X, so supplied flag bytes include duplicate effective states.
DP alternates0/1B00; initial OAM contents and Y vary with supplied flags.
All256 OAM bytes, A, hidden B, P, X, Y, SP, DP, DB and the source cursor match
the original machine code. Three executed mutants fail: wrong hide coordinate,
wrong final carry, wrong OAM destination. No injected-interrupt proof is claimed;
unaligned infinite-loop inputs are checked structurally, not run to completion.
Failed initial fixture assembly2188 is retained; it is not an oracle result.

Normal2191/instruction2192 also match their complete2,872-frame timeline and
PCM. All six measured hide calls have matching input cursor values and contain
no ordinary interrupt. First-call elapsed clocks fall7,038→1,704 (5,334 saved);
six calls total34,130→8,560. These clocks include emulator events, not exclusive
CPU cycles. Independent encounters differ:42 video rows,1,686 original-RAM
rows, one input row, and PCM differ between parent and trial. This is not an
equal-encounter whole-game speed ratio or a claim of unchanged game timing.

## Game results, including the remaining failure

- School run2187/audit2190: first scenery remains enable+8 versus NES+7.
  All four palette generations remain one frame late. Room/off-to-visible
  both29 frames versus NES34, but the fixed-offset fade gate still fails.
  The enable+7 collage visibly retains a black SNES frame beside NES scenery.
- Full traversal2193 completes8,874 frames. Forward entry2194 passes all40
  fixed background offsets in each of rooms1/2/3, first scenery+7 in each,
  and both whole-load latency checks. The parent2172 route timed out; different
  encounters mean completion alone cannot establish why this route succeeds.
- The school iteration's first fade service moves from+3 line238 to line234,
  but its final FAB8 main call still crosses NMI at+3 line240. That call has
  2,648 clocks outside the complete143,968-clock ordinary NMI. Its return and
  iteration reset therefore still occur on+4. This is the next scheduling
  boundary to investigate; do not change fade counters to hide the miss.

Full suite:1,060 tests pass (`/tmp/rcr-tests-2196.log`). Five new unit tests
check exact patch scope, all-bank original preimages, occupied padding,
repeat patching, actual assembled dispatch/store targets and special paths.
Review2195 validates164 current source bindings and19 served artifacts plus
its report. The collages were inspected; audio is supplied for audition, not
claimed subjectively pop-free from numerical analysis.

Whole-route scrolling/cadence, combat, shops/status, interrupt interleavings
and physical audio remain unqualified for this candidate. Keep it offline.

Follow-up: [palette comparator2197](PALETTE-COMPARE-SPEED.md) removes enough
additional loop overhead to restore the school return's exact NES fade.
Its scrolling/audio transport checks pass, but new strict combat evidence
still blocks promotion; neither this parent nor that follow-up was deployed.
