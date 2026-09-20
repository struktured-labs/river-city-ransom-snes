# Triangle cutoff and restart experiment — not deployed

The current Rival game ROM remains unchanged. This work modifies only an
opt-in standalone sound probe; it is not yet wired into `build_native.py`.

The legacy engine mutes triangle volume both in its packet synthesis and its
idle linear-counter/disable timer. Patching only the first path does not
remove the second hard cutoff. The inspected [Memblers source archive](https://membler-industries.com/SNES/2a03-src.zip)
has SHA256 `5a524d0e608721f705a0c625af6ceb054d0861e0a2508bdd52168773920c7d6d`.
The corresponding byte sequences are checked against our pinned binary before
patching. DSP gain behavior was checked in the local Snes9x `SPC_DSP.cpp`.

`triangle_dac_release_engine()` redirects both mute sites, freezes triangle
pitch, and linearly releases DSP GAIN. Active synthesis restores gain. It
does not key off, reset the triangle sample, or keep oscillating through a
fade. It is an approximation, **not NES analog-filter emulation**.

## Rejected first version

Release-only report878 preserves steady volume but makes restart sample jumps
worse at six of eight phase offsets. Example offset2: baseline restart251,
candidate1,466. A favorable offset0 alone would have hidden this regression.
This version is rejected for promotion.

Earlier attempts are retained:871 hit the diagnostic's exact engine-size
assertion;872 used the wrong restore gain and missed the idle timer's mute;
873 corrected those, before the phase sweep exposed restart regressions.
The harness now explicitly rejects fourfold gain and failed tone gates.

## More promising attack-plus-release version

Report879 adds a short linear attack and swaps mono VOL/GAIN scaling. Across
eight fixed offsets0/1/2/3/7/11/17/23:

| Maximum adjacent PCM step across the selected boundary windows | Baseline | Attack + release |
| --- | ---: | ---: |
| Note off | 1,872 | 252 |
| Note on | 1,622 | 253 |

Stereo tone/pitch/activity, sustained mute, restart and peak gates pass at all
offsets. Steady RMS increases approximately0.74% because full ramp envelope
is `$7FF`, versus direct gain's `$7F0` after scaling. No clipping occurs.

The strict per-event no-larger-step gate **still fails** at offsets11/17/23:
249→253,238→242,248→252 and236→237. Those1–4-unit differences are retained;
the gate was not relaxed to turn this into a release pass. Nor do these
measurements establish subjective click-free audio or NES waveform identity.

The alternate PCM-mixing/stereo-volume branch is unsupported by the new gain
scaling. Linear-counter expiry, short/repeated game notes, pulse/noise mix,
SPC transport budget and physical captured audio remain unqualified. No Rival
restart, OBS mutation, controller input or live-screen assertion this turn.

## Harness and reproducibility

`tools/audit_triangle_release.py` executes both SPC variants and an asset-free
NES reference with the equivalent enable/control/timer schedule. NES write
counts, RAM shadows and completed frames are checked. Every boundary retains
unchanged stereo PCM and full-scale waveforms, with the complete audio nearby.
No gain normalization or waveform alignment is applied. The separate clocks
and initial phases make NES edge metrics descriptive, not an equality oracle.

An initial multi-capture process retained NES oscillator/filter state across
library deinitializations. Each final capture now runs in its own process.
Report880 verifies all eight repeated NES WAVs and all eight baseline SPC WAVs
are byte-identical between final reports878/879;686 source/artifact bindings
match. Historical874–877 are retained, not silently overwritten.

Seven new unit tests cover exact patch boundaries/preimages, opt-in attack,
gain preservation, both audio channels, clipping and missing event coverage.
Full suite:659 tests pass. Both experiment reports retain
`isolated_gates_passed=false` and `release_ready=false`; CLI failure propagates.

Next: qualify short `$4008` rests and the supported game packet mode, then
test a disposable full-game candidate against unchanged gameplay timing,
audio transport and captured output before any Rival deployment.

Review: <http://127.0.0.1:8766/triangle-boundary-review-881/>.
