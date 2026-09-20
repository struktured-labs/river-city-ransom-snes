# Simultaneous duty/reset events: executed merge controls

`check_audio.check(..., paired=True, retrigger=True, reset_notes=True,
deferred_reset=True, reset_duty=True)` alternates pulse duty $3F/$BF every
32 driver frames while sending a note-reset flag at those same boundaries.
The existing explicit mute/restart/pitch phases remain. `pulse2=True` selects
the second voice; these are separate single-voice captures, not both at once.
All frames verify duty, timer, channel enable and periodic reset schedule.
The profile is `periodic-duty-reset`, so the constant-duty phase auditor
cannot accidentally treat it as the previous reference experiment.

Both voice variants pass tone/mute/pitch checks:
`build/combined-reset-pulse1-01`, `combined-reset-pulse2-01`.

`tools/check_reset_controls.py --deferred` executes the candidate and two
derived-ROM mutations. The first clears reset requests while leaving duty
requests intact; the second restores the old immediate duty KON sequence,
creating duplicates on combined duty/reset events. The oracle checks all
341 packet flags and the exact ordered key-on sequence. It counts legacy
immediate writes as extra events rather than silently excluding them.

Both suites pass their expected outcomes: good passes, missing-reset and
duplicate-duty controls fail. Observer and normal-core full WAVs match.
Audio/trace/receipt evidence:

- `build/combined-reset-controls1-01/index.html`
- `build/combined-reset-controls2-01/index.html`

This establishes one KON write per expected event under the exercised
combined duty/reset schedule, not exact NES duty-change waveforms or DSP
internal event timing. The explicit pitch change also carries a reset, but
arbitrary simultaneous pitch/duty combinations and both voices together
still need coverage before gameplay integration. No game/Rival change.
