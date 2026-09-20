# Current combined candidate: physical gameplay and native audio

2026-09-19. This follows the combined2367 deployment, rather than reusing
physical footage of an older cartridge. Previous goal turn made progress by
deploying and recording that build; this turn adds actual gameplay evidence.

Rival still runs `fa7e249a299cff42b8a296631af1f8aa9bd2a4ed0d8da753bf28ee21641f619c`
(compact-pair2242 gameplay +55 Hz splash, no rejected DC pulse experiment).
[Hardware review2420](http://127.0.0.1:8766/compact-game-hardware-review-2420/)
contains the recorded traversal, native PCM, exact decoded hold frames,
before/after screenshots, measured transients and all source hashes.

## Bounded physical episode

Preflight2377 verified idle OBS recording/replay, the expected cartridge,
unchanged saved SNES.CFG, and the1P menu. SNAC Yes bypasses USB P1 requests;
the initial Start request did not enter the game. After visually confirming
the OSD, runtime SNAC was temporarily set to No. Ordinary Start/Start/B inputs
entered the street; Start paused. No game RAM edit or cartridge restart.

The first screen guard2401 refused because the reference2398 was captured
before the pause labels finished settling. No traversal input was sent.
That refusal remains in the review. The observed settled pause screen was
visually audited and a new guard2402 passed without changed thresholds.
Both fresh guards2405 passed before recording and immediately before input.

Episode2404:22.7 seconds requested,16 seconds right/repeated A,4 seconds
left/repeated A, then pause, bounded within a30-second OBS recording.
Actual input receipts retain clock timestamps; they are not frame-exact game
consumption measurements. Recording:
`/home/struktured/Videos/drmario_sessions/20260919_005455_struktured_v6c_part2.mkv`.

Native2403/decode2410 contains2,399 complete callback pairs,1,919,200 stereo
48k PCM16 frames, exact source/common conversion, no large packets. It brackets
the entire input episode and owned OBS recording. Completeness does not prove
probe neutrality or device continuity. The debug monitor WAV is not substituted
for native DeckLink input PCM. Review video is silent stream-copy; WAV start is
not video start and no sample-exact synchronization is claimed.

## Scrolling observation, not full-speed certification

Camera2413 uses the existing fixed scenery ROI(340,160,1280,120),256 logical
pixels.1,792 decoded frames;1,784 accepted adjacent matches; seven rejected
pairs(539,543,597,615,623,631,645) retained. Nonzero measured movements:
86 two-pixel,25 one-pixel,1 three-pixel steps. Equal-step hold histogram:
46×2 frames,5×18,2×44,1×43,1×4. Both matcher sensitivity controls pass.

The four-frame interval1144→1148 remains unresolved. Exact frame context2417
shows enemy movement at1146 while roof scenery stays fixed; it is not an
identical whole picture. This does not establish whether the camera command
was held by gameplay or published late. Encoded PTS has one34ms interval
elsewhere, which is retained; OBS cadence is not hardware NMI timing.
Original-speed parity, worst-case graphics deadlines and the physical
camera-hold cause remain unproven.

## Sound: pause control and retained transients

Native2399/decode2406, recorded while the first input guard refused, contains
2,397 complete callback pairs and39.95 seconds of **all-zero native PCM**.
Same OBS process and source/common conversion verified. The separate gameplay
capture supplies a non-dead AC control in both channels. The first30 seconds
of each pass the existing pause-pair check; an inserted paused click fails.
This establishes silence in the sampled pause, not permanent pop-free output.

Transient2414 retains all six >=10ms zero spans, eight largest separated
sample steps and exact unnormalized clips. Maximum step4147, no clipping;
injected full-scale edge, clipping and50ms gap sensitivity controls pass.
The251.458ms quiet span near native26.7997s occurs near the final pause,
followed by a short sound, then sustained silence from27.17494s. These are
measurements, not proof of an unwanted audio dropout.

[Pause timing regression2418](http://127.0.0.1:8766/compact-pause-timing-2418/)
checks original NES status167 versus current speed-candidate status2358 using
actual PCM and verified frame/sample telemetry. Both have the separated
pause sound at **+57 frames**, after25 frames below the fixed10%-peak analysis
threshold. Native audition audio is unchanged. A two-frame delayed mutant
fails; dead capture is rejected. This demonstrates original delayed pause
sound timing, not sample-exact attribution of the independently captured
physical gap. Do not remove expected menu audio merely to eliminate silence.

## Handoff and next action

Latest handoff (06:45 UTC): after temporary camera-only diagnostic2547,
receipt2586 restores the same production2367 cartridge. SNAC Yes is verified
in2588;2592 shows the OSD closed at the1P/2P menu, not the earlier paused street.
[Camera trial2594](http://127.0.0.1:8766/late-camera-hardware-review-2594/)
improves internal moving-camera coverage but does not reproduce or explain
the production four-frame hold and is not an audio qualification.

Historical gameplay-capture handoff:

Screenshot2412 visually verifies SNAC **Yes**;2416 verifies OSD closed and game
paused on school street. Saved SNES.CFG remains
`066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
Recorder stopped, debug tap removed, adapter properties/links and OBS audio
routing restored. No physical SNAC-button test is claimed. All controls released.

Next obtain game camera-command/main-loop observations matched to the current
physical hold, and command-level context for the newly captured transients.
The earlier logger packet export describes an older encounter, not this one.
No gameplay ROM patch was justified by these measurements alone.

Full suite:1,120 tests pass (`/tmp/rcr-tests-2421.log`). Across the new physical
and pause-reference reviews,104 source bindings and50 served artifacts were
hash-verified; the hardware review was visually inspected in Chromium.
