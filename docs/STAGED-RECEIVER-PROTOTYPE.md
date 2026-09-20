# Executed staged receiver prototype4053

This is a real SPC700 fixture implementation, not a game ROM or release.
3955 and the default playable cartridge remain unchanged. No MiSTer, OBS or
physical SNES action. It implements packet isolation and explicit commit, not
the final presentation-clock protocol or a demonstrated sputter fix.

## Mechanism

The3955 receiver normally writes incoming bytes directly to DP40–56. That
cannot simply be held for later playback: receipt already changes active
state.4053 redirects only the receiver dispatch at0487 to new code3540.
All existing engine bytes are otherwise preserved. New code and a separate
23-byte buffer at3600 plus pending flag3617 extend the fixture image to12824
bytes. Current engine SHA is checked before construction.

Paired port bytes go to the staging buffer. Waiting for the next pair retains
the existing receiver-clock service. After final-token22 ACK, the pending
loop services the existing idle/timer/publisher using old active controls.
Only explicit port tokenD8 permits the23-byte copy to active state, followed
by unchanged packet-complete/adapter/translator handling. Pending is cleared;
ready7D is not published until completion. No packet flag is silently dropped.

The final-token ACK permits the SNES sender to return, but its **next** update
would wait for ready. Automatic timely consumption must therefore be proved
before game integration; this prototype is not permission to block game logic.

## Actual execution and negative controls

Core4055 appends a fixture sender API to the existing1093 SPC execution core.
It drives actual input ports, executes real SPC instructions, and snapshots
every pair ACK, the held packet, pre-adapter commit and final ready. It does not
replace the receiver or timers with host models. Core build41.228s. Preliminary
core4054 was superseded when adding the pre-adapter commit snapshot; no test
qualification is claimed for4054. Its earlier source binding is not reused.

-4056:24 cases, two frame modes × four pair delays(0/256/512/2048 clocks) ×
 three holds(64/1024/20000 clocks), pass in0.081s. All active23 bytes stay old
 at every partial/held snapshot. Staged prefixes and complete commits match
 exactly. Existing continuous half-frame deadline checks pass through holds.
-4057:202 successive varied packets,101 per mode, retain ordered bytes and
 pending ownership; no active-state leakage or volume-writer violations.
 Eight ordinary-protocol cases on untouched3955 match the old core's results
 exactly, including timer event sequences and packet costs. This is scoped
 fixture compatibility, not a full-game observer-neutrality claim.
-Four executed mutants fail: direct active writes; premature commit;
22-byte copy omitting final flags; removed hold-loop timer service.
 Qualification including these controls takes0.288s.
-Two patch tests pass0.002s: exact prior-engine preservation except dispatch,
 code/buffer separation, zero-initialized storage and changed/repeated parent
 rejection. The tests supplement rather than replace actual execution.

## Native audio fixture

4058 captures one pulse tone, holds its replacement for20000 SPC clocks, then
commits. Actual DSP pitch stays052C while held and becomes040C after commit.
All33168 native stereo sample frames are preserved in WAV byte-for-byte:
peak2307, no clipped samples, maximum adjacent step4152. No resampling,
normalization, trimming or forced emulated flush is applied. Terminal DSP
backlog is not claimed as captured. These metrics and the synthetic tone are
not game-music fidelity, a listening result or a pop-free certificate.

## Next implementation requirements

Replace explicit fixtureD8 timing with a bounded presentation-time contract
that works on physical SNES/SPC clocks. Keep staging isolated until consumption;
specify late/missing update, full-buffer and resynchronization behavior. Preserve
all original APU flags/order and timer ownership. Extend opcode/continuous
tests before integrating the protocol and upload length into the3955 game.
Then require same-core full-timeline/native-PCM observation, original NES
sound-onset tests, transition coverage and graphics/game-speed tradeoff gates.
No fixed-phase or added-latency acceptance is inferred from staging alone.

- [Native tone, actual bytes, failures and metrics](http://127.0.0.1:8766/staged-receiver-review-4059/)
- [Timing requirement](http://127.0.0.1:8766/current-audio-pipeline-review-4052/)
- [Audio issue6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6)

The evidence page was rendered and visually inspected. Full speed, scrolling
and pop-free audio objective remains active.
