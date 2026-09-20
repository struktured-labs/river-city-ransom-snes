# Executed original NES periodic-reset reference

The asset-free NROM fixture now has an opt-in `NES_RETRIGGER` profile.
Duty $3F, timer $00FD and channel enable are held fixed, except explicit
mute at frame 120, restart at 180 and pitch change to $007E at 240.
Every 32 driver frames, including disabled-channel periods, it writes the
pulse high timer $4003. Frame/phase, length status and periodic-write count
are captured from NES RAM. The default disabled-reload fixture is preserved.

`--suppress-retriggers` replaces only the periodic `STA $4003` with
`STA $0206`, preserving instruction size and CPU cycles. The two executed
ROMs differ only in the two address bytes at file offsets 181 and 182.
Initialization, mute/restart/pitch writes are not suppressed.

Evidence: `build/nes-retrigger-reference-02` and
`build/nes-retrigger-suppressed-02`, each with complete WAV, timeline, ROM,
hash-bound report and audio HTML. Their timelines are exactly equal.
Their PCM is identical until sample 27959, seven samples into the callback
containing driver frame 32 (samples 27952..28750). This localizes the first
audible-signal divergence to the first periodic reset. It does not by itself
score the correct post-reset phase or compare NES to SPC output.

The original FFT-max tone gate selected the stronger second harmonic in
the periodic-reset reference. Its failed result is preserved in the report.
The new independent fundamental-period check requires >0.9 normalized
recurrence within about 1.5% of the expected period and <0.8 at half that
period, rejecting octave-up ambiguity. Existing activity, amplitude,
clipping and near-zero-run checks remain required. Both variants pass these
tone/mute checks; a no-reset control is NOT supposed to fail tone presence.
The earlier failed FFT-only capture remains `nes-retrigger-reference-01`.

Unit tests cover the correct fundamental, octave up, octave down, silence
and a stronger second harmonic. All 145 Python tests pass. The default NES
ordered disabled-reload regression also passes in `nes-reload-regression-03`.

Run `tools/check_nes_disabled_reload.py --retrigger --core NES_CORE --out
FRESH_DIRECTORY`, optionally adding `--suppress-retriggers` for the control.
Next: use these executed reset/no-reset waveforms to validate the isolated
reset-aware SPC implementation. No game ROM, default or Rival change.
