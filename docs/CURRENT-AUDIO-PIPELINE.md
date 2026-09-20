#3955: generation and delivery measured separately

Fresh observer4051 leaves the exact3955 cartridge unchanged and preserves all
9,090 same-core primary video/input/state frames and every native PCM sample.
The existing sparse observer is reused; no emulator mutation was needed.
The new wrapper additionally binds the actual selected core's source files.
Capture plus verification took38.305s; analysis4052 took6.549s.

## Coverage and independent checks

All8,641 packets are paired with actual CPU acknowledgements and complete SPC
receipt/ready events.8,156 packet records have a wrapped FA54→FA64 driver call;
485 do not. This count is specifically the observed wrapper, not a claim about
every original sound-bank entry. All7,342 frozen stable intervals decompose;
all1,298 other intervals and their prior classification remain explicit.

CPU entry spacing plus four signed cost changes (original driver, post-driver,
bridge setup, transfer) equals CPU sender-completion spacing exactly. Separately,
SPC receipt spacing plus signed post-receipt processing change equals ready
spacing exactly. No cross-clock origin is fitted. Every SPC gap reproduces
the frozen3962 audio audit. Missing driver-return and missing-ready mutations
fail; two focused unit tests reject missing/duplicate/censored pairs and a
damaged decomposition. The report was rendered and visually inspected.

The historical common-wrapper classification called both paths “early.” That
label is deliberately removed here:5F00 also serves the regular IRQ. Actual
entry scanline, retained flag and depth remain in every record.

## What makes the current worst gap

Packet8037, CPU frame8486:

- CPU sound-driver entry spacing:19.157833ms.
- Extra driver execution versus preceding update:+0.473803ms.
- Extra transfer time:+0.754099ms; bridge setup:+40 master clocks.
- Actual SPC receipt spacing:20.386626ms.
- Post-receipt processing changes1.077754→1.548845ms (+0.471091ms).
- Actual SPC-ready spacing:20.857717ms.

These are elapsed observations, not exclusive instruction-cycle costs. Ready
is a protocol event, not an acoustic-onset marker. CPU and SPC endpoint gaps
are not interchangeable: packet7075 has the longest measured stable CPU sender
completion gap, while8037 has the longest SPC-ready gap.

Stable CPU cost distributions:

|Stage|Median ms|Maximum ms|
|---|---:|---:|
|Original driver|0.657719|2.662163|
|Post-driver|0.064254|0.066116|
|Bridge setup|0.022256|0.022908|
|Transfer|1.048085|2.140868|

Across all8,641 packets, receipt→ready processing is0.527661–1.908747ms,
median1.241612ms. Thus changing only command ACK latency cannot remove the
earlier CPU phase variation or the later variable SPC processing.

## Concrete next experiment and limits

Every selected stable packet completes CPU transfer on lines58–160, without
crossing the driver's CPU frame. The latest is packet6583, frame7017,
line160/cycle942. This suggests a bounded deferred-consumption experiment on
the SPC side, instead of another CPU busy wait or interrupt phase guess.

For feasibility only, a line200 target leaves0.587753ms after that latest CPU
completion **plus the globally largest observed SPC processing time**1957ticks.
This arithmetic uses the core's nominal clocks; it is not a proven physical
CPU/SPC synchronization bound, all-scene deadline, or safe implementation.
Transitions and the1,298 excluded intervals are not covered by this margin.

Before changing the production engine, prototype a bounded pending-packet
buffer with an explicit presentation-time protocol. Preserve all23 original
APU bytes and event flags, prove no overwrite/loss/reorder, retain timer/volume
ownership, and leave the SNES CPU free to run game logic. Inspect whether the
receiver currently mutates active state before an update can be deferred.
Do not just delay a ready flag while DSP state is already being changed.
Quantify sound-onset latency and transitions as first-class tradeoffs, including
same-core native PCM and original NES onset tests. Clock drift, underrun and
resynchronization need explicit policies and failing controls.

No buffering, new audio protocol or timing fix is implemented by this diagnostic.
3955 remains unchanged; no hardware/default-ROM/release promotion. Full speed,
scrolling, broad graphics coverage and pop-free acceptance remain open.

- [All stages, every interval and native-audio link](http://127.0.0.1:8766/current-audio-pipeline-review-4052/)
- [Audio issue6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6)
