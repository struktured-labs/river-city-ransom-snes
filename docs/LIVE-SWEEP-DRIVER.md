# Live sweep driver integration

Follow-up: [retained NMI/camera fix and recorded Rival trial](RETAINED-NMI-CAMERA-CURRENT.md)
supersedes the deployment state below. The original failed evidence remains historical.

September 18, 2026. Implemented and running in an experimental game ROM;
**not deployed** because the speed gate fails. Rival's last deployed ROM remains
`071c89e9dde88bcc5622ef6379522149e72415b51b3418a8f281f5a66774733f`.
No physical input, restart, OBS change or new hardware capture in this turn.

[Review: six untouched frames and four native-rate audio excerpts](http://127.0.0.1:8766/sweep-driver-review-1131/).

## Implementation

`--experimental-sweep-driver` integrates the previously executed sweep kernel
and CPU event hooks with a continuous SPC clock and a single mono pulse
pitch/volume publisher. It requires paired fast-reset audio, rejects competing
sweep/duty modifications, and remains disabled by default.

Timer 0 has a four-count target (512 SPC clocks). The residual clock is retained
across half-frame deadlines and advances independently of sweep enable and raw
timer writes. Both pulse dividers share this clock. Four/five-step half-frame
intervals are 8543/8545 and 8543/12814 SPC clocks, respectively. Five-step resets
also clock immediately. The mode/reset arrives at packet publication, not at
the original NES write cycle; 3/4-CPU-cycle reset delays and exact hardware
frame-counter edge blocking are not reproduced. Rounded timing uses the pinned
Snes9x NTSC SPC rate of 1,025,280 clocks/sec.

The paired receiver polls the clock while waiting for CPU data. It temporarily
restores the active sweep controls during those polls, so a half-frame cannot
consume partially received control bytes. The adapter applies explicit write
events after reception and clears packet metadata before legacy key-on logic.

The publisher uses live swept periods, continuous underflow/target-overflow
muting, and existing constant/envelope volume state. Legacy pulse-volume writes
are redirected to scratch to prevent transient conflicting updates. Existing
key-on, duty, noise and triangle behavior is retained. Idle publication is
skipped unless a half-frame or envelope change requires it; each complete
packet still publishes. During a stalled packet, clocks advance but DSP pulse
publication waits until the complete packet.

The expanded engine exceeds bank C0's remaining space. Only this option moves
the image to checked-unused ROM bank D2, uploaded with long indexed reads.
The current image is 12,415 bytes. Graphics, controls and splash assets are
unchanged. A disabled rebuild, branded identically, matches Rival byte-for-byte
(`build/sweep-driver-disabled-branded-1100/`).

## Executed tests

`build/sweep-driver-executed-1111/report.json` records actual SPC instructions:

- 615,120 residual/step/mode/timer-delta clock cases.
- 2,097,152 period/control/enable pitch and muting cases, both voices.
- 1,088 envelope/constant cases and 35 idle-update checks.
- Real boot, hardware timers, paired reception, synthesis and idle execution:
  one second in each 4/5-step mode, with both immediate and delayed senders.
- Three executed damaged engines rejected: slower timer, missing five-step
  immediate clock, and a restored conflicting legacy volume writer.

The real-time check independently counts all fully elapsed deadlines; it does
not infer expected event count from the observed list. Final partial deadlines
are explicitly censored. The tested maximum event offset improved from 1,213
to 674 SPC clocks after idle optimization. This is not measured acoustic latency.

Optimized CPU producer proof `sweep-driver-producer-1125` passes 6,144
generic/direct and 4,096 fused cases, with both executed faults rejected.
The unit suite passes **796 tests**; `git diff --check` passes.

## Game candidate and retained failure

Latest ROM: `build/sweep-driver-branded-1120/native-cpu.sfc`, SHA-256
`289cb49da2db286a8bd4941286139e0ddde013eb7c1a52a225189398d441aff8`.

Normal capture 1121 completes the four-room route in 9,568 frames. Actual-SPC
capture 1124, main-loop capture 1122 and renderer capture 1123 each match the
complete normal audio and frame/RAM timeline. Transport audit 1126 checks all
9,101 received packets, 5,948 sweep-related CPU write events, key-on rules and
completion order. Post-final-byte processing takes 458–1,705 SPC clocks.
Three trace corruptions are rejected as well.

Cadence audit 1127 **fails**, without waiving any irregular starts:

| Room | Complete stable loops | Native ticks per loop | Three-frame start gaps |
| --- | ---: | ---: | ---: |
| 0 | 598 | 2 | 1 |
| 1 | 1,740 | 2 | 1 |
| 2 | 469 | 2 | 0 |
| 3 | 1,086 | 2 | 0 |

Both park directions have zero short 1/3/4-frame uniform-endpoint camera holds;
all longer stops remain in the report. Two-tick loop counts alone would have
missed the lost physical frame starts. A three-tick data mutation is rejected.
Earlier integration attempts 1101 and 1110 also failed their cadence gates.
Their different total route lengths are not equal-work speed ratios.

## Concrete interrupt-return finding

Neutral instruction capture 1130 and
`build/sweep-driver-lost-edge-1132/report.json` isolate the first missed service:

- Frame 2012: camera completion masks NMI at line 144, cycle 1276.
- Retained original interrupt work reaches `nmi_rti_return` at line 242,
  cycle 342, after the new VBlank edge.
- The return path starts polling `$4212` at line 242, cycle 1218.
- It reads the register **603 times**, then restores `$4200=$80` only at
  line zero after wrap. No native NMI entry or `$4210` read occurs inside
  the masked interval. Frame-end native tick count does not advance.
- The main loop consequently starts at frames 2011 and 2014, not 2011/2013.

The previous camera re-enable fix applies to an *unretained* return. This path
executes the retained game interrupt and reaches the ordinary NMI epilogue's
separate VBlank wait. Blindly deleting that wait is not validated: an earlier
global no-wait experiment regressed, documented in `NMI-RETURN-WAIT-EXPERIMENT.md`.
Next work is an executed fresh-versus-acknowledged event fixture for this exact
return path, including late publisher deferral, stack restoration and nested
service safety, followed by full-route recapture.

## Audio evidence, not a sound-quality pass

NES replay 1129 executes all 41,066 ordered writes from the latest observed
candidate, grouped by publication frame. It retains its quantization and
15,181 writes shifted to a later publication frame; no original sub-frame
timing claim is made. The review includes two six-second park excerpts from
both systems, at original 32,040/48,000 Hz with original sample values. No
normalization, resampling, time stretch or fitted alignment; no clipped samples
in these excerpts. This is not a perceptual-pop or hardware qualification.

Combat sputtering, strict graphics-publication timing, and full-game original
speed remain open. Keep the active goal open and Rival unchanged until the
candidate clears the speed gate and raw hardware audio is tested.
