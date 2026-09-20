# Physical menu audio and full-route transient follow-up

Rival remains on branded616 (`34835f8`). This follow-up changes diagnostic
tools, tests and evidence, not the cartridge. No restart, controller input,
OBS recording/replay action, scene change or gain change was performed.

## Actual recording versus the same-ROM no-input reference

`static-arm-rival-45s-622.wav` is a stereo48kHz read-only extraction of the
ongoing Blackmage OBS MKV, seconds43465..43510, spanning the preceding menu,
the authorized restart, ident and new menu. The source is
`/home/struktured/Videos/drmario_sessions/20260916_214537_struktured_v6c_part2.mkv`.
The independently checked physical ident begins at43473.08.

`static-arm-menu-622` executes2,400 no-input frames of this exact ROM on the
pinned normal Snes9x core. Its receipt binds ROM, core, harness, screenshot and
raw PCM. This uses the existing render-capture mode, whose status only covers
video callbacks, not game correctness. The first native-mode attempt stopped
at frame300 because that old monitor treats preboot splash RAM as game RAM;
it produced no passing native receipt. Full game/fault evidence instead
remains in the existing branded route captures with authenticated one-way
boot monitoring. No fault check was relaxed.

`tools/audit_hardware_menu_envelope.py` explicitly allows a limited calibration:

- Locate the emulator ident's first10ms energy bin above40 PCM and use the
  physical ident onset to establish the recording neighborhood.
- Search only +/-40ms in1ms steps, using the **first four menu seconds**.
  Choose one constant offset and two fixed channel gains. Require an interior
  correlation above0.9. Retain every candidate score.
- Freeze those parameters; evaluate the following **24 seconds**, both
  channels. No time stretching, holdout alignment or holdout gain fitting.
- Use exact sample-grid boundaries, avoiding cumulative rounding drift at
  32,040Hz. Listening files remain unmodified at their native rates.

Current report `static-arm-menu-envelope-626` finds constant offset6.986sec
between the files, channel gains approximately0.3467, held-out correlations
0.96266/0.96262, normalized energy errors0.15819/0.15829. There are **zero**
10ms bins where expected energy exceeds150 PCM but recorded energy is below
20% of that prediction. The plot displays every left-channel bin without
smoothing; the report retains both channels.

Four actual PCM mutations in the held-out region are rejected without
refitting:10ms stereo silence,20ms left silence,50ms right silence, and100ms
clock slip. Tests also cover held-out corruption leaving calibration
unchanged, truncation, short coverage, out-of-range alignment, silence/DC,
dead channels, nonfinite data and fractional-rate boundaries.

This is a **large missing-energy/coarse cadence diagnostic**, not proof of
sample-equivalent synthesis, absence of smaller clicks, matching NES timbre,
or pop-free gameplay. Calibration thresholds are explicitly diagnostic, not
a new acoustic release gate. File offset is extraction metadata; nearby OBS
settings do not authenticate immutable historical routing.

## Complete gameplay discontinuities and delivery gaps

`static-arm-branded-transients-626` checks all5,177,636 stereo sample frames
across9,712 display frames. No missing callbacks or clipping. The largest
adjacent-sample step is4,494/32,768 (0.137146), below the existing independently
executed isolated-NES bound0.171656. There are1,139 key-on event packets in
1,133 display frames. Full-scale spikes and missing callbacks remain detected;
the report exposes20 strongest-event clips and complete unchanged PCM.
Different rates, output levels and filtering prevent this bound from being
a perceptual equivalence test.

The transient audit now uses the full capture verifier, contemporaneous
trace bindings, the same exact known-ident startup model as the SPC audit,
and checks the recomputed key-on verdict. Source hashes are retained.
`static-arm-branded-spc-624` revalidates all212,405 actual received bytes.

`static-arm-branded-gaps-624` inventories27 intervals above1.5 nominal frames
over the whole route. All6 sufficiently long gaps have exactly zero PCM in
the fixed interior (five frames after the previous packet, two before the
next). This excludes a sustained nonzero note across those measured interiors,
not every transition edge or short gap. Stable unpaused park gameplay still
has no long packet gap under the separate eligibility check.

523 Python tests pass. The intermittent gameplay-pop complaint is still open;
these results narrow the hypothesis, not erase the report. Next useful work
is a reproducible current gameplay event or an independently demonstrated
channel/synthesis mismatch—not suppressing legitimate note resets solely
because they produce the largest waveform steps.

Review:
<http://127.0.0.1:8766/static-arm-menu-envelope-626/> and
<http://127.0.0.1:8766/static-arm-branded-transients-626/>.
