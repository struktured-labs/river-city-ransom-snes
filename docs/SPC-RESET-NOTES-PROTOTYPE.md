# Isolated reset-aware pulse prototype

`paired_engine(..., reset_notes=True)` appends a 16-byte routine at SPC
$301F and redirects the paired receiver's final jump to it. The routine
computes packet reset flags $56 AND enable $55 AND 3, writes nonzero bits
to DSP KON, then enters the original synthesis at $0496. X remains 23.
Engine size is $2C2F. Only `check_audio.check(..., paired=True,
retrigger=True, reset_notes=True)` selects it; game builds do not.

Candidate `build/spc-reset-notes-01/script.sfc`, SHA256
`4d94a53b794792cf2449bc41daec64ddb3879abf79ff0dd8bd58b7a0a9e0dd13`.
Tone/mute/restart/pitch checks pass. Executed observer confirms new KON writes
at packet IDs 1,33,65,97,181,193,225,241,257,289,321 (PC $302C).
Muted reset packets 129 and 161 do not produce KON. The unchanged original
duty-change path also writes KON on initial packet 1, so simultaneous
duty/reset handling still needs review before any game integration.
Observer full WAV matches the normal-core capture byte-for-byte.
Evidence: `build/spc-reset-keyon-01.{csv,wav,json}`.

## Executed NES comparison and controls

`build/retrigger-phase-audit-01/index.html` contains four unmodified audio
captures and waveform plots. Five same-pitch events (32,64,96,192,224) use
fixed windows 2..10 ms after the callback end. No waveform shifting or
inter-event phase alignment. Fourier phase at the known fundamental is
measured on each channel; magnitude of the mean unit phasor measures
repeatability, not exact phase agreement between systems.

Both channels produce:

| Variant | Phase repeatability |
| --- | ---: |
| Executed NES reset reference | 0.99302 |
| NES same-cycle suppressed reset control | 0.17883 |
| Legacy paired SPC | 0.13823 |
| Reset-aware SPC prototype | 0.98763 |

The scoped audit requires positives >0.95 and controls <0.5. This establishes
repeatable phase restart for this isolated constant-pitch pulse case; it
does not establish exact BRR phase, duty waveform, dynamic pitch ordering,
envelope behavior, both-pulse interaction or perceptual gameplay fidelity.
All 145 Python tests pass. Next: pulse-2 and simultaneous duty/pitch/reset
cases, matched negative mutations, and only then game integration. No Rival
or default ROM change.
