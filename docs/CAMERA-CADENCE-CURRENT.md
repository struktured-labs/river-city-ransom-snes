# Camera cadence versus apparent slowdown

Superseded by [earlier stationary-camera arming and Rival deployment](STATIC-CAMERA-ARM-CURRENT.md).
The retained590/no-deployment status below describes the preceding experiment.

Retained experiment remains camera-first590, SHA256
`b319afd1069370737b9e9940a5b3e2cabe6956195c4cadf64a5307a648e20aeb`.
No new Rival deployment/reset.507 Python tests pass. The prior turn fixed
camera publication; this turn adds whole-route execution evidence and rejects
another faster-transport combination. It does not certify full-game speed or
audible/physical sound fidelity.

## Extra-frame stale camera: full-route check

`tools/audit_camera_hold.py` examines every active, same-room frame with the
same committed camera at both consecutive frame boundaries. All160 actual
street renderer lines are required; missing lines and timeline gaps fail
closed. It does not select a later prettier frame or replace the old warnings.

`camera-hold-605`:6,384 checked frames, zero stale-camera failures. The actual
old582 capture is the negative control: frame8485 still renders250 while
both surrounding committed values are248. Full observed timelines and PCM
remain identical to their own normal-core captures. This is a scoped
extra-frame-hold test, not proof about every intra-frame camera transition.

The old sweep's four settling warnings include revisits: it subtracts the
first-ever observation of a camera position from its first later stable
observation, even if the game left that position between them. Values628 and
420 therefore must not be described as continuous publication delays. The
old report/gates are retained unchanged; this new independent renderer check
does not silently relabel them as passes.

## Original execution cadence, not image animation

Fresh `cadence-nes-599` captures original E2B1 writes to F6 across the complete
8,548-frame route. The existing read-only CPU observer is now hash-bound by
the capture process itself. Fresh `cadence-snes-599` captures the translated
camera-tail entry across8,629 frames. Both entire timelines and PCM equal
their corresponding normal-core controls.

`audit_camera_cadence.py` checks observer sources, linked span definitions,
trace bounds/order, scenario identity and neutrality. It measures every
adjacent camera-calculation interval wholly within the active east/west park
sweeps, including intermediate-frame eligibility. Time uses actual CPU/master
clocks divided by nominal NTSC clocks/frame, not rounded frame-number gaps.
No enemy state is forced to match and no speed ratio is inferred from total
route duration. Reports retain every interval and exclusions.

| Route/system | Intervals | Mean frames/update | Maximum | Standard deviation |
| --- | ---: | ---: | ---: | ---: |
| East NES |401|1.999850|2.353251|0.108552|
| East paired590 |427|1.999388|2.412636|0.123054|
| West NES |307|1.999643|2.379107|0.112206|
| West paired590 |318|2.000408|2.295260|0.111957|

Source-bound report: `cadence-audit-605`. This supports approximately two
display frames per camera calculation in these traversals, with update jitter
on both systems. Different encounters still prevent matched combat-speed
certification. The SNES integer frame-number gaps alternate1/3 sometimes;
those are not necessarily a three-full-frame stall.

Fresh short movement capture599/audit600 also passes the existing strict
rightward movement oracle: both advance21 pixels, every NES target reached
no later on SNES. It remains only24 Right frames plus8 settling frames, not
bidirectional/combat coverage.

## Faster sound transport tried again, not promoted

Candidate601 enables existing three-port transfer on590, paired disabled;
no sound-engine/DSP or game-asset change. Fixed602 completes9,403 frames;
normal/observed adaptive602 complete8,696 with exact timeline/PCM neutrality.

Cadence-triple-audit605: east413 intervals, mean1.997435, maximum2.310253,
standard deviation0.120023; west370 intervals, mean2.000418, maximum2.322795,
standard deviation0.112282. Different encounters mean these are not paired
per-call savings. In particular the east minimum0.991090 remains visible.

Entry603 rejects it: whole loads21/29/29 versus retained20/28/29 and NES
20/31/30; first visible offset8 rather than7 in room1. Faster transfer alone
does not justify regressing loading. No new full renderer or actual-receiver
qualification is claimed for601, and it stays unpromoted.

## Next measured target: stationary-camera main-loop interruption

Neutral CPU capture `cadence-cost-600`, frames7154..7162, profiles an early
park interval where both working and committed camera are0. Frame7160's
camera hook is at line56 after the previous hook at7157/line222. The original
main loop still begins every two output frames in the observed window.

`cadence-cost-audit-606` binds all six original top-level call intervals.
The F299 actor call accounts for256,496 of331,716 elapsed clocks in that
iteration, **including its interrupt**, not exclusively actor instructions.
The intervening NMI-to-sound interval is48,884 clocks; sound driver15,334;
restore-to-sender1,162; sender-to-camera41,414 including remaining game work.

The scheduler's armed flag is0 at both frame boundaries; its scheduled count
is unchanged. `camera_deferred_nmi_exit` only arms after the first real
camera/table difference, so stationary-camera actor work does not yet use
the retained-NMI path. This identifies an experiment to evaluate, not a
proven safe policy change. Any earlier arming must preserve transitions,
original interrupt counts, audio service and all current graphics gates.

Review: `http://127.0.0.1:8766/cadence-review-607/`.
