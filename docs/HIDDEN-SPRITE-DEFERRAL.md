# Hidden sprite preparation: guarded saving, scrolling regression retained

Experimental twelve-row candidate: `build/hidden-sprite-on-373/native-cpu.sfc`,
SHA-256 `77b8609eeb44224b0372a8ce8dc3b445be624887f87cc341e93df903b2f68d6d`.
**Not deployed or promoted.** Room 2/3 fades now match all forty NES offsets,
but room 1 remains late and the fresh background/route regression fails.

## Guard and implementation

`experimental_hidden_sprite_defer` is default-off and requires hidden direct
rows. At `prepare_sprites`, an initialized producer in transition state 2
checks the next row cursor. Only exact row flag **1** (dirty, not queued)
with a nonzero initial-publication requirement permits skipping directly to
CHR preparation. That required row cannot be retired by the consumer until
a subsequent producer prepares it, so the screen cannot be revealed yet.
Sprite source dirtiness, snapshot cache and pattern-half cache stay untouched.
The first producer without that blocker converts the current original sprite
input before the consumer can finish the transition. Initialization is never
skipped, and ready/queued rows do not qualify.

The disabled build `hidden-sprite-off-373` is byte-identical to parent 365:
`84a48c63c1966ed0609bb107bee220b3ca2f81d4bd739e60f46987dd1c613074`.
The new option changes neither original graphics nor game counters.

## Executed checks and measurements

`hidden-sprite-publisher-oracle-378` passes **106 cartridge cases** and rejects
five mutants. Coverage includes cursor wrapping, both sprite pattern halves,
different source bytes, all row states, required/nonrequired rows, initialization
and hidden/visible states. It checks the old snapshot/cache and dirty latches
after deferral, then all 544 converted and actual OAM bytes after refresh.
Ten cases execute the real publisher: it must retain state 2 with the required
unqueued row, then retire the prepared row, finish the transition and upload
fresh OAM. A forced early-reveal mutation is rejected along with incorrect
queued-row, nonrequired-row, initialization and dirty-latch behavior.

Initial fixture 370 had incorrect WRAM addressing and an incorrect expected
coordinate mapping; it failed and is not counted. Publisher fixture 375
omitted the production full-transition scan and correctly failed its completion
assertion. The corrected 378 oracle above is the qualified result. 431 Python
unit tests pass separately.

The full instruction-observed replay `hidden-sprite-park-374` and normal replay
`hidden-sprite-normal-374` contain identical 9,408-frame timelines and PCM,
checked by `hidden-sprite-profile-377`. The bound stage trace shows three
hidden sprite stages taking **306 master clocks** each; the last hidden
stage still does full current preparation (15,862 clocks). Parent observations
range from 12,100–15,898 clocks per hidden sprite stage, but independently
evolving game work prevents treating those as paired equal-work measurements.

`hidden-sprite-park-audit-377` passes stable unpaused park packet cadence.
`hidden-sprite-audio-377` verifies all **9,222 completed-NMI packets**, no
unfinished tail and no unflushed writes. Full PCM and transition-gap clips
remain available; physical/pop-free audio is not certified.
`hidden-sprite-status-audit-381` passes both Present Status entries with zero
pixel differences and correct numeric values.

## Fade comparison, including rejected larger batches

| Hidden rows | First scenery, rooms 1/2/3 | Whole load, rooms 1/2/3 | Differing fixed fade offsets |
| --- | --- | --- | --- |
| NES | 7 / 7 / 7 | 20 / 31 / 30 | Reference |
| 12 | 8 / 7 / 7 | 24 / 30 / 29 | Room 1: 7/11/15/19; rooms 2/3 exact |
| 14 | 8 / 7 / 6 | 24 / 30 / 28 | Room 1 unchanged; room 3 early at 6/10/14 |
| 16 | 8 / 6 / 7 | 25 / 29 / 29 | Room 1 unchanged; room 2 early at 6/10/14/18 |

All three pass their scoped park packet gate, and all three fail overall
loading/fade acceptance. Reports: `hidden-sprite-entry-377`,
`hidden-sprite-14-entry-381`, `hidden-sprite-16-entry-381`. No per-room budget
tuning or shifted image comparisons are used.

## Fresh scrolling test fails — no inherited parent pass

`hidden-sprite-background-audit-383` covers **698** common positions
(259/114/110/215 by room). Both original and expanded background checks fail
at park cameras 255 and 371: respectively 3,007 and 3,933 differing pixels
in the original strip. The larger region differs at 6,942/9,237 pixels.
Original screenshots and independent background planes are retained.
No late native scroll publication is reported, but the settling and complete
route gates also fail. Both observers remain neutral and the known bad ROM
is still detected. Do not call this a scrolling pass.

The SNES outward waypoint completes; on the return trip Alex loses all power
(visible in `hidden-sprite-single-normal-382/frames/frame-08320.png`) and
respawns from room 3 into room 2 at frame 8404. The unchanged policy then
times out at frame 9953. Neither timeout nor death is concealed by injecting
health, recovery input or a longer limit.

The first background mismatch is already on the outward trip (SNES frame
7748 versus NES 8398 at the selected camera), so death does not explain all
image failures. Diagnostic RGB555 overlap comparison identifies a two-pixel
horizontal offset at camera 255. Camera 371 is also shifted but not completely
explained by a four-pixel overlap check. These diagnostics do not replace the
unshifted failures or change acceptance. Trace actual displayed scroll next;
the earlier parent 365's 789-position pass is not inherited by this ROM.

## Updated CPU target: the second iteration

The first fade initialization now occurs at rendering-enable offset 3, as
on NES. The remaining initial-color delay occurs in the following iteration,
not the old first-iteration location. The instruction audit now supports an
explicit zero-based `--iteration` selection without changing the observed run.

`hidden-sprite-second-iteration-382` observes the next F293..F2B4 sequence from
frame 2124 line 169 to its fade call at frame 2126 line 92. Matched calls total
610,432 clocks, including 282,690 in ordinary NMIs. The game-update call has
175,488 residual clocks; sprite-list work costs 85,806; the FA9A call is also
interrupted. Frame-end RAM shows NES advancing its fade tick at offset 4,
while this port does so at offset 6. Preserve the game's ordering and timers
while reducing that work. Whole-load room-1 latency, combat/endurance,
the two background offsets and physical gameplay audio remain open.

Follow-up: [renderer and CPU traces](RENDERED-SCROLL-DEADLINE.md) now confirm
that both background failures are missed line-32 scroll deadlines. The old
scroll is used through line 158, then the second HDMA entry applies the new
value. The original image failures and incomplete route remain unchanged.
