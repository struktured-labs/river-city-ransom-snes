# Shop-entry sustained-audio comparison

Candidate is unchanged `blank-drain-01` (SHA256
`98616f8db81c8e575121fdbfb6df17f2ba461cacdf2bd84aa180adaa94928605`).

The active PCM inside its raw 6068–6079 delivery gap is not sufficient
evidence of a missed mute. In the original FCEUX shop trace
`build/reference-shop-01/hardware.jsonl`, frame 6009 writes pulse controls
`$4000=F3`, `$4004=F1`, and noise `$400C=30`; the next audio-register writes
at 6018 change pulse controls to F0 and triangle to 80. Pulse volumes were
nonzero immediately before the original write gap. `$4016` controller writes
are not audio events. This does not provide a sample-exact mapping between
the FCEUX trace and the separate FCEUmm PCM capture.

`tools/audit_phase_audio.py` now retains complete same-input-phase clips,
per-frame audio measurements, sample boundaries, source/clip hashes and
end-of-phase screenshots. It validates both captures and original ROM
identity. There is no time/gain fitting or best-match window search, and
no fidelity-pass label. Missing/discontiguous phases are rejected by tests.

Review `build/shop-entry-audio-comparison-01/index.html`: original
`shop-exit-route-01/nes` versus `blank-drain-exit-01/snes`, all 180 frames
of `enter_shop`. Both sustain active audio over most of offsets 35–71.
The original has a brief low-energy frame at offset 58 (AC RMS 2.49),
while the port has no equally quiet frame in that interval. Its source
register mute is later (raw 6088, with subsequent publication), and its
phase PCM reaches silence later. These timing differences remain visible
in the report; this is not an aligned music or mute-timing pass.

Conclusion: do not forcibly mute every multi-frame shop-entry packet gap;
the original itself retains nonzero pulse volumes across its corresponding
write gap. Loading/sound-service timing and synthesis fidelity still need
work. This investigation does not clear the reported random popping.
No ROM changes or Rival deployment. All 110 unit tests pass.
