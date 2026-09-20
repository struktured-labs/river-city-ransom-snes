# Actual DSP startup repair and Rival trial

Follow-up: [short silence replay against actual NES filter input](SHORT-REPLAY-SILENCE.md).

September 18, 2026. Test build `fa882cb61138` is now running on Rival;
previous ROM retained. [Video, unchanged screenshot collage, voice plots and
native audio](http://127.0.0.1:8766/pulse-onset-rival-review-1363/).

## Verified defect

The default-off postpublication-KON patch described in
[the prototype report](POSTPUBLICATION-PULSE-RESTART.md) now has actual DSP
voice-start evidence, not just register-write ordering. Audit1342 compares
identical 2,512-packet streams. All403 game restart identities and final target
pitches match;402 have active target volumes. Wrong first oscillator pitches
fall315→0, onsets with nonzero stale-pitch output27→0, and stale samples510→0.
The worst old onset has30 stale samples. This is a specific startup repair,
not a perceptual all-pops verdict or original-NES waveform equivalence.

The host-only observer records actual KON consumption and96 following V4
samples per voice. It checks hardware startup delay,32-clock sample spacing,
and one-to-one linkage to actual KON writes. Raw DAC equals delivered PCM;
complete WAV, timeline, RAM and final image match independent unobserved runs.
Every received packet byte/site matches the fixture. Wrong-pitch and missing
observation mutations are rejected. Reproduction patch and observer live in
`tools/snes9x-pulse-onset.patch` and `tools/snes9x_pulse_onset.inc`.

The prior full-mix sample-step comparison remains mixed:84 improvements,
2 ties,141 regressions. Its native clips remain available. These are ordinary
mixed-channel edges, not a reliable click detector; no unfavorable result is
discarded. BRR startup-pointer fidelity remains outside this onset check.

## Regression and physical trial

Candidate1321 changes45 ROM bytes, all within SPC code and checksum; no
CPU game code, graphics, branding or sample assets changed. Cadence1327
passes3,550 stable loops across four rooms at two ticks/two-frame starts,
with no short irregular park holds. This is sampled, not full-game speed proof.

Boot1336 stages the SHA-named cartridge and verifies remote hashes. Trial1352
records22.7 seconds of ordinary USB movement/jump requests within30 seconds of
raw plus OBS recording. Actual recording is
`20260918_123152_struktured_v6c_part2.mkv`; review video1360 is stream-copied.
Camera1362 measures1,790 frames,1,783 accepted pairs and six rejected pairs.
Equal-step holds are26×2 frames and8×26 frames, with no short1/3/4-frame holds.
This different encounter does not resolve the older physical four-frame hold.

Raw/AAC audit1361 fits one offset using seconds4–7. Five held-out windows
correlate0.99863–0.99931. A dead-monitor negative and100ms AAC-only cut are
detected. The branches share Blackmagic/OBS, so this establishes capture
agreement, not independent analog-fidelity or pop-free proof.

Two AAC silences at8.916s and9.1027s last10.67ms and24ms; corresponding raw
silences last19.31ms and29.94ms. Their command-level cause is still unverified.
Pause/recording-edge gaps also remain in the report.

## Handoff

Game paused on school street, SNAC visually restored Yes in1357, OSD closed
in1359. Remote process names the new launcher and remote cartridge SHA is
`fa882cb61138dac8a08bd3be7f71bf27153309f929e89d269764a7098e973d62`.
Saved SNES.CFG remains
`066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
Owned recordings stopped, raw tap removed, OBS routing/settings restored.
Controller presets and splash bass were not changed in this iteration.

Next: command-level attribution of remaining short physical silences,
original-reference synthesis fidelity, and broader combat/transition trials.
