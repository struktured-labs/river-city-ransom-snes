# Automatic pulse-length diagnostic

`tools/check_audio.py --length` runs the pinned SPC engine with the same
scripted pulse/mute/restart/pitch packets as the default test, except pulse
control is $9F rather than $BF: constant volume remains enabled, length halt
is cleared, and $4003's length index remains zero. It requires an audible
stereo onset and a silent tail after 100 ms without a software $4015 mute.
The explicit mute phase is still a separate control. Dead audio cannot pass
the onset requirement.

The reference length-table semantics are visible in the pinned FCEUmm
`src/sound.c`: index zero loads ten half-frame counts, and the pulse length
counter decrements when control bit $20 is clear. The legacy upernes host
`source/asm/Sound.asm` calls `emulate_length_counter` before sending its packet;
the present native port does not implement that host processing. That legacy
code must not be copied blindly: its square-zero reload reads SNDTMP4013,
and its frame-based timing is not an exact NES frame-sequencer implementation.

## Executed result

`build/audio-length-final-01/report.json` fails all three note-expiry phases;
the explicit mute control passes. Diagnostic ROM SHA:
`22a5035360c22847c77acc0638352d5eb14ff2815878183fef3f1c8be9c84af2`.
The final note's late-window RMS is approximately 1914 on both channels,
remaining active in every 10-ms window. This proves that raw register packets
alone do not make this pinned engine provide the requested automatic expiry.
It is not a measured comparison against an executed original NES test ROM yet.

The default pulse/mute/restart/pitch profile still passes in
`build/audio-default-recheck-01`. Fifty unit tests pass, including controls
rejecting a never-ending note, a silent onset, a dead stereo channel, and a
too-short onset capture. The new diagnostic deliberately returns nonzero on
the current implementation; it is not relabeled as passing or used to weaken
the existing audio gates.

## Relevance to RCR's reported sputter

Do not treat this missing behavior as the proven cause. In
`build/late-io-quality-01/snes/timeline.json`, the pulse-1, pulse-2 and noise
control bytes all have length-halt set throughout the sampled menu (60 frames),
idle/walk/attack (180 frames each), and pause-requested (180 frames). None of
these sampled channel controls requests automatic length expiry. Other game
effects remain untested, and this does not cover triangle linear counters,
sweeps, envelopes, or DMC.

For the observed sampled soundtrack, cadence and register-update/retrigger
semantics remain higher-priority suspects. Adding counters clocked from the
still-variable original game tick would not establish NES timing fidelity.
This checkpoint changes diagnostic code only, not the game audio runtime or
Rivalmage deployment.

```sh
python3 tools/check_audio.py --core /path/to/snes9x_libretro.so \
  --out build/new-length-probe --length
```

## Periodic-retrigger/dropout follow-up

`--retrigger` retains the constant-volume pulse test but sets the note-start
flag every 32 diagnostic frames. A WRAM counter records actual scheduled
triggers; the capture verifier requires it to equal floor(driver_frame/32).
This makes missing scheduled execution an error, not a passing quiet signal.

The tone oracle now also measures consecutive near-zero samples independently
in each channel. The active-tone limit is 0.5 ms; a synthetic 1-ms dropout
fails even though the existing 10-ms activity gate accepts that window. This
threshold applies only to controlled sustained tones, not arbitrary music
rests or waveform shapes. The explicit mute gate still requires silence.

Both `build/audio-retrigger-final-01` and `build/audio-fine-final-01` pass.
Active windows show at most one near-zero sample (about 0.0312 ms at 32040 Hz)
in either channel. Periodic retriggering therefore does not reproduce audible
dropouts under this steady diagnostic update schedule. This is not a matched
NES waveform/phase-reset oracle, nor evidence that gameplay SFX are correct.
The length-expiry defect and full envelope/sweep/triangle/noise/DMC requirements
remain open.

CI now executes the periodic-retrigger profile in addition to the standard
SPC profile. Fifty-one unit tests pass. No game audio runtime or Rivalmage
deployment changes are made by this diagnostic follow-up. Long game interrupt
gaps during loading remain a concrete cadence problem to address next.
