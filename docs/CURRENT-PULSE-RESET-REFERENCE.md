# Current-engine pulse resets: eight executed NES comparisons

Review: <http://127.0.0.1:8766/current-pulse-reference-review-2312/>.
No production-ROM, Rival, OBS or controller changes. The preceding turn made
progress by reconstructing selected DSP edges and finding two pulse-2 startup
boundaries. This follow-up tests the actual current engine, not the older
isolated reset prototype, against a broader original-platform reference.

## Implemented diagnostic

`build_current_pulse_reference.py` builds asset-free NES and SNES players with
eight held-tone cases: all four duty settings at periods `$00FD` and `$06C6`.
The latter period with duty3/control`$FF` appears in physical packet23/505, where
the previous trace found the retained pulse-2 restart edges. The artificial
stimulus isolates that channel; it is not a replay of the complete game episode.

Each case has128 source frames, an initial note, and high-timer resets at local
frames33/65/97. Both finish with60 muted frames. There are1,084 frames per run.
The SNES player embeds candidate2242's exact authenticated SPC bytes; no sound
driver, sample or transport modification is made.

Controls suppress **only the24 periodic resets**. Initial note/duty changes
remain. NES periodic writes are redirected from `$4007` to disabled pulse1's
`$4003`, preserving CPU instruction/data count; pulse1 stays disabled. Its full
frame/sample/count/status timeline equals the real-reset reference. SNES controls
clear the high-timer event and reset flag, retaining all other packet bytes.
Both systems' PCM is identical before the first periodic-reset callback, and
differs afterward: suppression has an actual waveform effect. Suppressing
resets is a diagnostic control, not an acceptable port fix.

## Fresh executions and observability

Fixture2300 produces four complete normal runs2301–2304. Filter observers2305/2306
preserve NES timeline, PCM and RAM exactly; the independent recurrence checker
reconstructs875,308 native filter samples in **each** run. Filtering is neither
bypassed nor fitted. This is the pinned local FCEUmm reference, not NES hardware.

SNES onset observers2307/2308 preserve same-core timeline, PCM, RAM and image.
Every1,084-packet stream matches actual reception and raw DAC matches delivered
PCM. Normal has32 eligible pulse-2 restarts (eight initial plus24 periodic),
control has exactly eight. Both have zero wrong first pitches or stale nonzero
onsets. All32 system/variant tone cases pass the unchanged fundamental-
recurrence check; this is not exact waveform or analog-filter equivalence.

## Retained failure: low-pitch narrow duty

The existing transient checker supplies the thresholds unchanged. It measures
the three fixed reset callbacks per case, at native48kHz NES /32,040Hz SNES,
without phase/time/rate/gain alignment or waveform normalization.

Seven of eight cases pass these **bounded signal metrics**. Period`$06C6`,
duty0 fails the relative-step limit:

| Measurement | NES reference | Current SNES |
| --- | --- | --- |
| Maximum reset-callback adjacent step |4,784|2,309|
| Whole-case absolute peak |5,538|2,309|
| Step / peak |0.863850|1.000000|
| Allowed SNES ratio |reference +0.02 =0.883850|**fails**|

Its absolute step is smaller, but that does not waive the normalized shape
failure. The hardware-context case `$06C6`, duty3 passes with ratio1.0 against
limit1.034648. All cases pass clipping and the existing0.5ms near-zero-run bound;
the observed SNES startup run is five samples,0.156055ms. None of these tests
proves subjective inaudibility or resolves a physical pop.

The fixed pre-reset steady windows also preserve a substantial SNES DC bias:
roughly−1,778 at low/narrow duty versus NES−16; low/duty3 is roughly−1,249 versus
NES+24. Means depend on window/cycle count and are reported, not optimized or
removed. This exposes another synthesis/filter difference worth investigating;
it does not establish that DC correction alone would match NES or fix the user's
symptom. Original samples and engine remain unchanged.

Next audio work has a concrete failing current-engine fixture. Investigate its
BRR waveform/DC and reset boundary together, preserving real resets and checking
all duties/pitches before promoting a change. Do not turn down the entire mix or
smooth the audit audio to make this numerical gate pass. Full speed/scrolling,
current-cartridge menu regression and physical qualification remain open.

## Evidence and checks

Review2312 contains32 untouched native audio clips, eight fixed-scale waveform
pairs, all failed/passing gates, DC/tone measurements and bindings. Plot origins
are reset **callback starts**, explicitly not exact cross-system APU-write times.
All33 source hashes,41 served artifacts and32 exact source slices were verified;
the failed-case plot was inspected in Chromium.

Injected full-scale spikes and1ms dropouts in actual candidate PCM are rejected.
Four new unit tests protect the channel/metadata mapping, same-cycle suppression
scope, native window/DC handling, silent/mutated signals and the retained failing
threshold. Full suite: **1,103 tests pass**, `/tmp/rcr-tests-2313.log`.
Passing unit tests do not override the deliberately failing audio-reference gate.
Preliminary2309/2310 are retained;2312 adds authoritative visual evidence.
