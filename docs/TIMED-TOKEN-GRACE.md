# Integrated audio: bounded fast polling — candidate4108

The previous integrated receiver4098 completed the full route but failed
release checks:12 three-frame mall intervals and a33.833ms maximum stable
ready gap. Frame3187 had no audio service call; CPU traces showed long
sound-service pauses between packet bytes.

Candidate4108 keeps the staged receiver and immediate-commit sender from
the4098 line, and adds a16-iteration SPC token-arrival window at `$3720`.
Arriving bytes are acknowledged without running full idle envelope/sweep
work between them. Exhausted polls still enter the original `$3700` idle
path so stalled transfers keep servicing timers. This is a receiver-local
change, not an emulator-scheduler change.

ROM SHA256 `57c62e5e9f5e6a112e6a72889beba87d85510bff40e5c3182533ef38f6653da7`.
Parent is early-OAM live-half3955. Not promoted, not deployed, not a default
ROM replacement.

## Measured full route

Review: <http://127.0.0.1:8766/timed-token-grace-review-4115/>

Normal4113 and same-core observer4114 match the complete primary timeline
and native PCM. Replay31.083s / total37.481s. Native DAC4,847,100 stereo
frames, peak6601, clipping0, max adjacent step4420. Untouched WAV is on
the review page.

| Room | Intervals | Frames/interval | Busy | Gate |
| --- | ---: | --- | ---: | --- |
| School0 | 598 | all2 | 0 | pass |
| Mall1 | 1,746 | all2 | 1 | pass |
| Alley2 | 477 | all2 | 0 | pass |
| Park3 | 847 | all2 | 0 | pass |

Stable ready gaps15.313–18.084ms, median16.553ms, over7,342 stable
intervals (1,352 excluded). Previous4098 was14.724–33.833ms with12
three-frame mall intervals.

The one mall busy frame is3323; both adjacent intervals still take two
frames. Encounters differ from4098 and from original NES; this is not a
matched-speed comparison.

## Focused guards retained

- Isolated timed-receiver footprint/deadline unit tests pass.
- Arrival-delay sweep4112:132 cases around the16-iteration boundary,
  including starvation risk, pass in0.177s.
- Prefix mall replay:1,144 school/mall intervals all two frames; audio
  service now runs on former miss frame3187.

The 3252 sprite-cycle harness was run against4108 and rejected as
`Unsupported OAM transfer` because this lineage uses256-byte live OAM,
not the544-byte linear copy that cycle assumes. The failed4116 prefix
is retained; it is a harness mismatch, not a 4108 cadence regression.

## Combat

1P running-jumps4117, scored with the same including-busy/stable-room gate
as3955: **1,710 / 1,710 two-frame, off-cadence0**. The earlier 8/7/3 NMI
loops are excluded transitions (camera 511→0 and 0→512), matching how
3955 treated its own strict-gate failures.

2P (4120, P2 active 2,382 jump frames / 798 attack frames) **fails** that
gate: running-jumps 14 three-frame intervals in stable mall, sustained-attacks
3 in stable school. Loop-clock median 663,308 vs 3955's 638,898 (~24k extra
master clocks, about11 scanlines). Start line walks 174→224 then misses.
Both players move. This is a 2P load regression vs3955, not the 1P mall stall.

A64-iteration poll trial4127 produced **identical** 2P jump cadence and
clocks to the16-iteration 4108 (same14 off frames, same median). The extra
cost is not missed byte-arrival polling. Isolated132 delay/starvation cases
still passed on the64-iteration engine. 4127 is retained as a negative.

2P span4137 around the first jump stall (2920–2935): `wait_port0` is a
steady ~23–34k master clocks every frame, including the 3-NMI frames. The
slip is cumulative 2P work starting at line 174 and walking to 224, not a
single long APU wait.

Immediate-commit 4139 (same engine, port3=0, no V-counter helper) **clears
2P jumps** (1,731 two-frame, off 0, median 633,002 vs 3955's 638,898) but
**worsens 2P sustained-attacks** (10 stable-room 3-frame intervals at
camera 0 vs 4108's 3 vs 3955's 0). Its 1P full route still passes all four
rooms; ready gaps 12.151–20.773ms (looser max than 4108's 18.084ms).
Commit timing is a jumps-vs-attacks tradeoff, not a 2P solution. 4139 is
retained, not promoted.

## Menus

Present Status4121 vs NES167: **pass**, 0 mismatched pixels on open and
reopen. Pause cursor4122: lingering HELP after reopen is cleared (glyph0,
0 pixels vs NES on reopen/gameplay). `pause_close` has718 mismatched pixels
because the SNES snapshot still shows the full selector while NES is already
mid-fade; cancel/reopen/gameplay match. Known lingering-cursor ROM still
fails.

Shop-repeat4133 vs NES91: **pass**, 0 pixels on both YES/NO prompts and both
post-purchase screens. Known stuck-prompt ROM still fails.
[Review4136](http://127.0.0.1:8766/timed-token-grace-shop-repeat-review-4136/).

Shop-NO4134: YES/NO cursor glyphs and prompt pixels match NES on all nine
checkpoints; confirming NO does not spend money on SNES. The oracle still
fails because P1 HUD reads `$20.60` vs NES `$20.00` (10 money-region pixels).
That is a pre-shop encounter difference, not a NO-purchase bug.
[Review4138](http://127.0.0.1:8766/timed-token-grace-shop-no-review-4138/).

## DMA

Same-core observer/control 4130/4131 match the 9,092-frame timeline and
native PCM. Audit4132: **52,470 general DMA envelopes pass** (50,543
VBlank, 1,923 forced blank, 4 other). Latest visible end256. Active-scanout,
crossed-frame and unfinished-transfer mutations fail. HDMA is outside this
observer. [Review4132](http://127.0.0.1:8766/timed-token-grace-dma-review-4132/).

## Still open

2P combat cadence, shop YES/NO oracles, staged onset/restart ordering,
popping, NES-matched speed, and physical SNES Junior/EverDrive play.
`release_ready` remains false. 4108 is the 1P experimental trial ROM.

[Previous failed4098 review](http://127.0.0.1:8766/integrated-timed-audio-review-4103/)
· [Audio issue #6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6)
