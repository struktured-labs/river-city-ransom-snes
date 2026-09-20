# Slower fixed-note splash ending

Follow-up: [harmonic WUB revision](HARMONIC-WUB-TAIL.md) adds stronger
overtone opening/closing over this same55 Hz tail, with before/after audition.
The2367 deployment and earlier captures below are historical baseline evidence.

The later camera trial was also restored to this same2367 sound/game build
at06:18 UTC (receipt2536); SNAC Yes and the OSD-closed1P/2P handoff were
checked2538/2540. See [camera evidence](CAMERA-RECORDER-QUALIFICATION.md).

## Latest audition handoff (2026-09-19, 06:11 UTC)

Restored the existing combined2367 build after the temporary camera-recorder
startup trial; restoration receipt `build/sub-wub-restore-2490.json` verifies
the cartridge, launcher and unchanged saved settings. The running launcher
was checked separately, and screenshot `/tmp/rcr-sub-wub-input-2495.png`
visually confirms SNAC **Yes**. No new sound revision was introduced during
this handoff: it is the already measured55 Hz, three-pulse ending below.
All11 focused wub-tail/hardware-review unit tests pass. The prior hardware
audition remains the audio evidence; this restart was not a new audio capture.

## Current Rival deployment: combined speed + sub-bass (2026-09-19)

Rival now runs `build/compact-sub-wub-2367/native-cpu.sfc`, SHA
`fa7e249a299cff42b8a296631af1f8aa9bd2a4ed0d8da753bf28ee21641f619c`.
This combines compact-pair2242 gameplay with the deeper55 Hz ident through
intermediate2366. It does **not** include the rejected zero-DC pulse experiment.
Boot receipt2372 verifies the uploaded cartridge and launcher, observed running
launcher, and unchanged saved SNES settings. The previous cartridge is retained.
No controller input was sent; the captured handoff shows the1P/2P selection menu.

[Hardware audition and boot evidence](http://127.0.0.1:8766/compact-sub-wub-hardware-2375/)
includes native unnormalized48k stereo PCM, before/after emulator auditions,
the recorded boot as silent video, and the unchanged OBS handoff screenshot.
Native2371/decode2374 contains2,390 complete callback pairs and1,916,904 frames,
with exact native-to-common conversion. Reacquisition packets and timing
residuals remain in the decoder report; no gap filling or continuity guarantee.

All five physical **tail** checks pass: measured55.32/55.15/55.18 Hz,
peaks146/175/205 (29/30 nominal frames apart), trough ratios0.206/0.195/0.072,
final decay and no clipping. The first independent silent-onset anchor is14.99s.
**The broader physical report is not an all-pass:** checkpoint124 in the quiet
pre-tail dip has a79.12 Hz spectral peak versus70.07 Hz programmed pitch
(12.92% error; the older constrained estimator is also outside5% at8.39%).
The other11 checkpoints pass. Echo from earlier pitches may dominate this
quiet window; that explanation is not established and the failed gate remains.
Subjective timbre approval is still the user's, not inferred from measurements.

Offline audits2369/2370 pass: all950 non-audio observations and game audio
after splash handoff match the speed candidate. Recorder cleanup and unchanged
OBS audio routing were verified. Neither this splash capture nor menu handoff
certifies physical gameplay speed or pop-free gameplay audio.

Full unit suite:1,118 passing (`/tmp/rcr-tests-2376.log`). New reviewer tests
reject non-native input formats and ensure a passing tail cannot hide a failed
glide check. All47 source bindings and seven served review artifacts were
hash-verified; the browser review was visually inspected.

## Deeper sub-bass audition (2026-09-19)

New optional candidate `build/sub-wub-trial-2331`, SHA
`473bb34c20cbf249d242594ae1d2125105edd13fe9af34df09730daa15fee698`,
lands an octave lower at55 Hz. Three existing30-frame pulses follow the
continuous descent; a30-frame volume dip approaching the landing separates
the first pulse from the slide's echo. Direct sound stops at219, with the
remaining21 frames draining the existing echo. Only ident automation and
the cartridge checksum change. Gameplay/synth/graphics code is untouched.

[Native before/after audition](http://127.0.0.1:8766/sub-wub-review-2333/)
includes unnormalized stereo PCM and hash-bound measurements. All10 gates
pass: measured notes55.35/55.19/55.18 Hz, peaks146/175/206 (29/31-frame
spacing), trough ratios0.206/0.188/0.080, no clipping, clean decay. All950
non-audio capture rows match the previous2089 build exactly, as does PCM
from game handoff onward. This is emulator evidence, not subjective approval
or a physical hardware audio qualification. **This older standalone candidate
was not deployed to Rival; the combined deployment above supersedes it.**

Retained first attempt2327/report2330 failed peak spacing. An added unit
negative control also exposed octave ambiguity in expected-pitch-constrained
autocorrelation; the new auditor uses a broad35–350 Hz spectrum peak instead
and rejects the actual previous110 Hz recording. Old auditors/evidence were
not rewritten. Incomplete2329 contains only audition clips after a JSON
serialization error; it is not a qualified report. Twelve targeted tests
cover envelope, fixed pitch, stop, edit boundaries and existing splash tests.

The original2089 deployment and physical failure below remain historical
facts, not a claim that this new candidate is already running.

User requested a wubbier ending: constant low note, slower WUB WUB WUB, then stop.
Trial `build/wub-tail-trial-2089`, SHA
`57a046b683c4ec157e4a7e56d3ed4a249cb8feb45110eb8f84c96f504f1c3bc6`,
was previously running on Rival. Boot receipt2095 verifies uploaded ROM/launcher hashes,
running launcher and unchanged saved SNES settings. No controller input was sent.

- First144 automation frames preserve the previous smooth descent exactly.
- Remaining tail holds pitch451 (about110.1Hz), three deep amplitude pulses
  nominally30 frames apart. Direct volume stops at219; echo decays until239.
- Existing two-voice synthesis, echo, graphics and gameplay code are unchanged.
- Builder only patches the final288 table bytes and cartridge checksum.

## Evidence, including failures

[Audition and recorded boot](http://127.0.0.1:8766/wub-tail-review-2099/)
contains native hardware PCM, emulator before/after samples, RMS graph, silent
stream-copied OBS video, handoff screenshot and source-bound JSON.

Offline audit2093 passes:950 frames of graphics/game RAM/timing match the parent;
descent PCM and all audio from game handoff onward match byte-for-byte. Actual
PCM shows three deep pulses, fixed low pitch and decay; the previous shallow
tail fails the new deep-pulse gate. Earlier2092 failed a one-frame RMS timing
measurement; the retained2093 checker uses a fixed50ms energy window to avoid
tracking individual110Hz waveform cycles. This is not audio processing.

Physical native capture2094 / decode2098 contains2,391 complete callback pairs,
1,918,214 stereo48k S16 frames. Source/common conversion is exact. The first
onset after2s silence occurs14.74s into capture; all12 pitch checkpoints match
within5%. Recorder cleanup and unchanged OBS audio settings are verified.

**Physical audit2099 does not pass all gates.** Three deep pulses, fixed pitch
and final decay pass. Loudness peaks at nominal notes147,174,204 give27/30-frame
intervals; the existing28–32-frame spacing gate fails the first interval.
Peak-to-trough ratios are0.156/0.159/0.062; pitch111.37/110.34/110.34Hz.
The analysis uses nominal60Hz windows rather than observed hardware VBlank.
No threshold was widened and no timing correction was applied. Callback
completeness does not certify sampling continuity/probe neutrality. Subjective
timbre approval remains with the user; this is not a pop-free release claim.

Full suite after physical reviewer:1,031 tests passed (`/tmp/rcr-tests-2100.log`).
Three new tests cover late boot anchoring, first-onset selection and refusal of
captures without the required silent reveal. Targeted six-test suite also passes.

## Unfinished speed work retained separately

The subsequent [saturating-shift trial](SATURATING-SHIFT-TRIAL.md) now has executed
arithmetic and game evidence, including retained failures. It is still offline.
At that historical stage Rival used regular1699 gameplay with only the new tail;
the current deployment at the top of this page supersedes that state.
