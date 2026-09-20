# Staged receiver game integration: not yet promotable

The receiver is now integrated into actual game ROMs, rather than only SPC
fixtures. No default ROM, MiSTer or hardware release was changed.

## Startup failure and correction

4073 (beam200) and4075 (immediate control) both fail after the branding handoff.
Their completed failed captures4074/4076 are retained. Read-only serialization
4077 preserves the entire4076 primary timeline and native PCM exactly. SPC RAM
contains a partly uploaded engine at frame320 but the engine is zeroed by340;
the CPU reports the audio timeout at343. This is not a missing deadline ACK.

The old DSP initialization clears FLG to0 while clearing registers, temporarily
allowing echo writes before restoring FLG20. Fixture4078 intercepts that write
at0BC7 and keeps bit5 set for register6C; other writes and the continuation0BCB
remain unchanged. This removes the observed boot failure. Hardware confirmation
and a wider startup-phase sweep are still required. The longer upload changed
timing and exposed this hazard; isolated powered-on fixtures did not cover it.

## Actual game results

-4079 delayed beam-relative build SHA
 `ed7092a5e3a8b4161710ad22b49f0325eb3b6ff074ebbc2b44c8dc2521624835`.
 Prefix4080 completes2578frames in6.127s replay,6.275s total, no reported faults.
 Full4081 fails the park-entry waypoint after8798frames. Final picture shows the
 school exterior. Do not classify this as full-route success. Observer4086
 reproduces the incomplete run and its audio hash, but its strict completion
 checker correctly rejects it; no completed observer report is claimed.
-4084 immediate-commit control SHA
 `eb84cd348f7e5bfcdad3bb18a5521503f8210db48218779c2ede5dac806ed78f`.
 Full4085 completes8942frames. Observer4087 proves complete same-core primary
 timeline/native PCM neutrality. Native DAC4766720stereo frames, peak5521,
 clipping0,max adjacent step3648. No listening/pop-free certificate.
 School room:582two-frame intervals and12three-frame intervals: **speed FAIL**.
 Other rooms:1910/558/731intervals, alltwoframes. Encounters differ from3955;
 these counts do not establish original-NES speed or acoustic improvement.
-4078 retains192timer/isolation/envelope passes in4082 and202ordered packets
 plusfive rejected broken-code controls in4083.

## Mechanism and next action

Builder updates the guarded IPL upload length, embeds the expanded engine,
and replaces sender LDY0 atC0D2CD with a C0F000 helper that returns Y0.
Immediate mode writes port3=0. Delayed mode reads both latched V-counter bytes
and sends floor((200-line)/8), or0afterline200. There is no CPU busy wait;
the coarse header is recalculated each packet, not a free-running SPC clock.
This is not exact synchronization, and may add source-to-sound latency.

The immediate control's speed regression requires measuring/reducing transfer
cost before accepting delayed scheduling. Existing per-token full idle service
is a suspect, not a proven sole cause. Keep the envelope/timer guards while
testing a cheaper receiver. Native audio and packet observers must support
staged copy explicitly: legacy direct-receiver packet IDs remain0and are not
valid packet-count evidence. None of these builds is approved for user testing.

[Audio issue6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6)
