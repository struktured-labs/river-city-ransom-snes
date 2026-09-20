# Reset flags do not establish pulse retrigger fidelity

The full current paired gameplay trace has 50 duty changes, 35 enabled
nonzero constant-volume changes, and zero such changes without a note-reset
flag. This was classified from the validated
`build/paired-game-bus-audit-02.json` packets. Duty-only suppression remains
unsupported as a fix for the reported game symptom.

A more important harness limitation is now exposed: the periodic-retrigger
signal test only verifies the CPU schedule and sustained tone/silence/pitch.
It does not verify pulse phase restart. Reports now explicitly mark
`retrigger_phase_behavior_verified: false` for this profile.

## Executed SPC write observation

`tools/snes9x_keyon_trace.inc` observes receiver byte 22 (packet/reset flags)
and actual writes through $F3 with DSP address $4C (KON). It adds no emulated
operations. Packet IDs are one-based; startup KON writes have packet ID 0.
Core `rcr_keyon_libretro.so` SHA256
`7e6157228cc9f9fe962d5fa06bc1168cd3337bcc03b312b42bac0ce545eb643a`.

For `build/paired-retrigger-02/script.sfc`, the 360-frame capture observes
341 packets, with pulse reset flags at packet IDs
1,33,65,97,129,161,181,193,225,241,257,289,321.
Some are during the explicit muted phase; do not label every flag audible.
After startup, the only pulse KON write is packet 1 at SPC PC $04C5.
There are no later KON writes despite the periodic flags. Full observer WAV
is byte-identical to the stock-core WAV.

The positive observer control alternates duty without periodic reset writes:
`build/paired-duty-keyon-control-01/script.sfc`. It produces pulse KON writes
at IDs 33,65,97,193,225,257,289,321, all at $04C5, as expected from the duty
change path. Its observer WAV also matches stock byte-for-byte. Thus an empty
later KON trace in the retrigger case is not simply an observer that cannot
see duty-triggered key-ons.

Artifacts: `build/retrigger-keyon-01.{csv,wav,json}` and
`build/duty-keyon-control-01.{csv,wav,json}`. CSV columns are event P/K,
packet ID, reset flags/KON value, post-operand SPC PC.

## Interpretation and next implementation requirement

Pinned FCEUmm `sound.c` SQReload updates `RectDutyCount[x] = 7` on a pulse
high-timer write, even when frequency stays unchanged. The inspected legacy
SPC constant-volume path does not use packet $56 to issue a corresponding
KON. This is a concrete discrepancy in retrigger handling and invalidates
any broad phase-fidelity interpretation of the old passing probe.

A DSP key-on is not automatically an exact NES phase reset: BRR start phase,
DSP key-on delay, waveform polarity and sample-loop behavior must be checked.
Next work should implement and compare an isolated reset-aware SPC variant
against an executed NES phase-reference probe before promoting it. No
claim that this discrepancy causes the reported popping, and no ROM or
Rival change in this investigation.
