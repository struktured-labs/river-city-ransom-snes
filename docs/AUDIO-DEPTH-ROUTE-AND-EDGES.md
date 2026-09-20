# Guarded scheduler: fresh route qualification and remaining packet jitter

Candidate3695 remains experimental, unchanged this turn:
`build/audio-phase-depth-game-3695/native-cpu.sfc`
SHA256 `60a73e42f287c3103b21751dca39cd37af1b3d7d31253da828b0979f855f636b`.
No deployment/default promotion, MiSTer, OBS or controller action occurred.

- [Current-cartridge route checks and complete native PCM](http://127.0.0.1:8766/audio-depth-route-review-3715/)
- [Eight ranked audio-edge clips and actual voice contributions](http://127.0.0.1:8766/audio-depth-edge-review-3719/)

Both pages were rendered and inspected. The edge01 native WAV returnedHTTP200.
No clips or acceptance comparisons were normalized, resampled, retimed or
aligned. The goal remains active: these results are not a full-game original
speed or pop-free certificate.

## Qualification on the guarded cartridge, not inherited results

Fresh primary3706 and renderer control3707 each complete9091 frames on the
park-single-sweep route. Audio/main3709 preserves primary3706's complete
video/input/state timeline and native PCM. DMA control3710 additionally matches
the primary core; observed3712 matches that exact DMA core's control. Renderer
3711 matches its own exact-core control3707.

Audits3713/3714 and parameterized qualification3715 establish:

- 7473 eligible rendered frames: zero missing coverage, split scrolling or
extra-frame stale-camera failures;6502 held-camera comparisons.
- 53072 general DMA envelopes:1923 forced blank,51145 VBlank,4 other. No unsafe
envelopes; latest visible completion259. Active scanout, cross-frame and
unfinished-transfer controls fail. HDMA is not covered by this audit.
- 8641 sound packets and1588 startup checks pass. No stale first pitch, split
startup configuration, misplaced startup volume or clipping in those gates.
- 3668 eligible room-loop intervals all take two frames:598/1746/477/847 in
rooms0–3. Busy-marked intervals are zero in these populations; every excluded
and censored record remains in JSON. This is not matched-NES-workload proof.
- Terminal deferred-scheduler accounting:7452 scheduled,7452 served, pending0,
fallback0. Counter balance does not prove every service met its time target.
- Current Present Status3708 passes numeric tiles and fixed-region pixels on
opening/reopening. Current663 pause IRQ-state checks and NES-matching native
pause onset are revalidated against their bound current-cartridge captures.

Qualification tool `tools/qualify_audio_scheduler.py` accepts explicit paths,
checks replay/cartridge/source bindings, and retains full records; it does not
copy green flags across cartridges. Its measured report/analysis time68.363s
is separate from replay time. Native full-route PCM:4,846,567 stereo sample
frames at32040Hz; peak6522, maximum adjacent step4321, no clipping. None of
those scalar measurements independently establishes acoustic quality.

## Largest current waveform edges

Plan3716 selects the eight strongest half-second-separated edges from the
entire unfiltered recording before observing voice internals. Full replay3717
is neutral, including all9091 frames/native PCM and identical DSP-write/raw-DAC
traces. Audit3718 reconstructs all2056 selected samples from eight DSP voices,
noise and the mixer, with zero split-pitch samples. Deliberately damaged noise,
envelope, volume and mixer records are rejected.

The largest step, sample1816764/frame3408, has unchanged voice controls and no
nearby DSP write. Its contributions are voice1 -1766, voice2 -36 and voice3
-2553 before the native mix. Four ranked events involve restart-related changes
including voice1 -2327; the other four have unchanged controls. Exact changes,
unmodified one-second audio clips and sample indices are retained in3719.
Successful reconstruction attributes these emulator edges; it does not prove
they are musically correct, acoustically NES-equivalent, or the physical pops
reported by the user. No gain reduction or blanket filtering was applied.

## Next causal target: service spacing

An additional diagnostic reads actual completed-packet DSP clocks from the
same validated observation. Across stable-gameplay intervals, completion gaps
range roughly9.8–23.7ms around a16.64ms median. This suggests residual scheduling
jitter is worth isolating; it does not by itself prove a dropped tick or audible
fault. `tools/audit_sound_packet_cadence.py` retains stable and excluded
intervals in report3720, rather than discarding transitions to earn a PASS.

Next separate original-driver entry timing, driver execution length and SPC
processing/commit time at the largest gap (around packet1728, frames2119–2121).
The existing sparse main-store observer can target FA54/FA64 to cover both
hardware-IRQ and direct-recovery service without a new full instruction trace.
Then decide whether to shorten the critical section, change the safe service
phase, or address a downstream timing problem. Direct-recovery context,
expanded combat/graphics publication and controlled physical audio remain open.
