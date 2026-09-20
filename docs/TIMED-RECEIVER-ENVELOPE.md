# Automatic staged audio receiver — fixture 4068

This is not integrated into the game. Playable graphics candidate3955 and the
default cartridge remain unchanged. No physical-console or listening acceptance.

4060 added a port3 deadline header to staged23-byte packets:0 commits after
receipt,1–32 counts existing consumed Timer0 ticks of512SPC clocks, larger
values clamp32. Late packets commit once complete. Old active controls stay
unchanged until the complete packet is copied. No host commit token is needed.

Two actual failures were fixed:

1. The holding loop omitted legacy0753 envelope work.4063 services both legacy
   envelopes and sweep/volume publication while preserving receiver X/Y. The
   actual old fixture remains level15 throughout a hold; the fix reaches11.
2. Sequential varied packets exposed five early commits in4063. Old-state
   publication after the timer read could leave unaccounted pre-arm ticks.
   4068 drains these through the existing active-control-safe receiver consumer
   at3284 before arming; the last zero Timer0 read is the deadline reference.
   It neither discards ticks nor resets the sound timer. Settling code3690,
   engine12977bytes. The failed4067 stream report remains intact.

## Executed qualification

-4069:202 varying ordered packets in two modes pass in0.086s. Five actual code
 mutants are rejected: frozen countdown, premature commit, omitted final flags,
 missing sound-timer advancement, and relatching the header on every pair.
 The last mutation reveals why deadline bounds alone are insufficient: arming
 must also occur before the first ACK, not after receiving the whole packet.
-4070:192 isolated mode/delay/header/initial-phase cases pass in0.238s, including
 continuous sweep timer guards and old-vs-fixed envelope negative control.
-4071:64 timed pulse-envelope packets captured at native32040Hz. All64 holds
 show envelope progress versus0/64 in4065. Full WAV/raw PCM equality checked;
 no waveform alignment, trimming, normalization or resampling. Old39396 versus
 new40827 stereo frames are retained, not made equal. Both peak2307, no clipping,
 max adjacent step4152. These are not game fidelity or pop-free metrics.

The relative deadline contract permits one512-clock tick of phase uncertainty
and1400clocks of processing slack. It is not yet a display-locked presentation
clock. CPU integration, upload length, resynchronization across transitions,
physical clock drift, native game audio, and graphics/game-speed tradeoffs remain.

[Native audio and results](http://127.0.0.1:8766/timed-settled-review-4072/)
· [Audio issue6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6)
