# Recorded-command replay rejects the centered-pulse trial

Follow-up: [current noise reference](CURRENT-NOISE-PACKET-REFERENCE.md) compares
the retained attacks to an executed NES state stimulus and measures the output
filter separately. The centered-pulse trial remains rejected and undeployed.

[Fixed-window waveforms, native clips and complete measurements](http://127.0.0.1:8766/dc-command-review-2350/).

The previous turn qualified the isolated tone and full-route timing checks.
This turn adds actual recorded-command evidence that changes the decision:
**do not promote DC trial2319 as a popping fix**. Rival was not changed.
This is not a subjective declaration that every larger edge sounds worse.

## Controlled replay

New fixture2342 changes exactly the32 SPC bytes from the qualified DC patch,
plus player checksum. It retains all1,238 physical commands from logger2079,
the exact sender CPU code, upload length and frame schedule of dispatch
fixture2277. Its engine is byte-identical to candidate2319's extracted engine.

Fresh captures2343/2344 run on the same pinned onset core as parent2280/2281.
Both independently validate actual received packets, neutral observation,
raw DAC equality,243 eligible pulse restarts, no wrong first pitch and no stale
nonzero onset. All46,365 DSP writes preserve exact clocks and values except
the2,478 expected GAIN31→35 writes. Completion times and complete frame/sample
timelines remain identical. Only the two gain registers differ at completions.

Fresh noise/rest stems2345–2348 preserve their normal run's entire timeline,
RAM and image. Noise PCM is sample-identical across engines. Noise+rest
reconstructs each actual full mix with only0/1 integer-rounding residuals.
This identifies what changed without assuming arbitrary linear mixer behavior.

## Same physical-event selection, same windows

The twelve events and frozen11.306-second lag come unchanged from review2290.
Eleven +/-20ms windows fall within emitted-command coverage. The event at
32.621438s remains outside coverage and is not assessed. There is no local
time/phase/gain fit, normalization or sample-rate conversion. Each window
retains both its parent's and candidate's peak location, not just whichever
location makes the candidate look better.

| Physical context (seconds) | Parent max step | Trial max step | Ratio |
| --- | ---: | ---: | ---: |
|18.760917|4366|4056|0.9290|
|12.902417|2753|2752|0.9996|
|16.730208|3436|4629|1.3472|
|15.764271|2711|3905|1.4404|
|19.523646|2972|2980|1.0027|
|20.274271|4218|5498|1.3035|
|12.251542|2630|3142|1.1947|
|13.421104|3111|3116|1.0016|
|14.733417|2245|2246|1.0004|
|22.279333|2480|2481|1.0004|
|20.783083|2335|2335|1.0000|

Four windows exceed1% growth, far beyond the +0.36% steady AC level change.
One improves materially; other tiny changes are retained rather than presented
as audible differences. The earlier seven-to-eight isolated-bound improvement
is real but insufficient to justify deployment. This is why the harness must
test recorded gameplay commands in addition to isolated signals.

The old physical recording is a context selector, not a waveform-phase match
to cold replay. No new hardware recording or physical causality claim is made.
Large steps may be intentional percussion/attacks; this report does not label
them all defects, nor does it certify perceptual improvement by minimizing them.

## Reproduction and next action

`build_dc_packet_replay.py` admits only the exact DC patch, not arbitrary
engine replacement. `review_dc_command_replay.py` checks source bindings,
command identity, timing, stem composition and both peak locations. Two new
tests reject unrelated engine edits and protect fixed-window regression
retention. Preliminary2349 was superseded after correcting duplicated unit
test discovery; its test-source binding is intentionally stale. Use2350.

The best speed candidate remains2242 with its prior audio engine. Keep the
centered-pulse candidate as a rejected experiment, not as the new default.
Further audio work must compare the original NES's treatment of these
specific note/noise attacks or establish a new physical defect; indiscriminate
edge smoothing would change intentional SFX and is not a faithful fix.
Current-game menu/transition and physical speed/audio qualification remain open.
