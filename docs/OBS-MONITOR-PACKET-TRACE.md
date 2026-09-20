# Same-run OBS monitor trace

Review: <http://127.0.0.1:8766/obs-monitor-review-1763/>

The five-clock SPC test cartridge remains on Rival, SHA
`0e9ba29becef5dc548a81d016d0e0311731244a3fc2cc8292db321c9dd2ac12d`.
No ROM changes or restart in this investigation. The game was exercised for
22.7 seconds of requested input, then paused; SNAC was restored to Yes and the
OSD closed. Saved SNES configuration and OBS audio settings are unchanged.

## Question and instrument

The previous physical capture had changing raw-monitor/AAC correspondence.
The exact OBS commit's [PulseAudio monitor implementation](https://raw.githubusercontent.com/obsproject/obs-studio/d97e5ad82/libobs/audio-monitoring/pulse/pulseaudio-output.c)
can return without processing a monitor callback when its playback mutex is
busy. That was a hypothesis, not an explanation established from source alone.

`capture_obs_monitor_packets.py` and `obs_monitor_packets.bt` attach bounded,
metadata-only uprobes to the hash-verified running OBS/DeckLink binaries.
They record DeckLink source submissions, monitor entries, actual trylock return
values, successful resampler output frame counts and callback returns. They do
not change OBS code, PCM, recording settings or controller input. Probes add
host overhead and can affect scheduling: observer neutrality is **not** proven.

The resampler probe is before queue publication. It does not prove queue writes,
PulseAudio/PipeWire consumption, recording-branch behavior or sample fidelity.
The audit retains unmatched input/monitor metadata, incomplete end callbacks,
busy locks, resampler changes and locked callbacks without successful resampling.
Missing lock events, orphan/duplicate events and malformed traces are rejected.

## Executed results

| Observation | Complete callbacks | Busy locks | Resampler frame changes |
| --- | ---: | ---: | ---: |
| Paused, short `1740` / audit `1742` | 298 | 0 | 0 |
| Paused, 40-second request `1741` / audit `1743` | 2,398 | 0 | 0 |
| Gameplay + dual recording `1750` / audit `1754` | 2,399 | 0 | 0 |

Every submitted packet matched a completed monitor callback exactly by source,
timestamp and frame count. Each had 800 frames at 48 kHz and yielded 800
resampled frames. No unmatched or censored callback was present. The gameplay
trace's callback interval, monotonic seconds 254364.72137–254404.68830,
brackets the local coordinator ready/input-complete interval
254371.78815–254395.56833. This is not a per-sample timestamp join.

The same gameplay capture **still fails fixed-offset audio correspondence**.
Training seconds 4–7 select offset 269481 samples with correlation 0.998691.
Held-out seconds 8, 10, 12 give 0.998951, 0.998915, 0.997746; seconds 17 and
19 fall to 0.676738 and 0.670778. Diagnostic searches retain delta zero through
second 15 and delta -32 from second 17 onward. The 50 ms windows place the
transition around 16.60–16.65 seconds; mixed windows are retained. No audio was
retimed, normalized or repaired to obtain a pass.

Therefore a busy monitor lock or changed resampler output frame count did not
cause this run's observed correspondence shift. The trace does **not** identify
which downstream branch changed timing, exclude waveform changes inside equal
frame counts, or explain the earlier uninstrumented run's larger shift.

Both the silent-monitor negative and the actual-audio injected 100 ms dropout
control pass on this episode. The earlier episode's failed control remains
failed; it was not overwritten or waived.

Six interior raw zero runs remain in the listening review: 25.458, 34.271,
159.625, 84.271, 18.479 and 14.979 ms. These are measurements of silence, **not
identified pops or proven dropouts**. This episode has no hardware APU command
log; musical rests, synthesis and capture causes are not yet separated.

The video matcher accepts 1,775 of 1,791 adjacent pairs. All 16 rejected pairs
remain: 851, 875, 883, 907, 915, 939, 963, 971, 989, 995, 1003, 1027, 1035,
1053, 1079, 1083. Equal-step hold histogram is `{2:47, 20:1, 18:5}`. This
different encounter is not identical-state A/B or original-speed certification.
The visually checked scenery ROI is `(370,160,1280,120)`, excluding actors/OSD.

## Artifacts and checks

- Observer: `build/obs-monitor-game-packets-1750/`; audit `1754`.
- Coordinated input/capture: `build/obs-monitor-game-1751/`.
- Recorder: `/home/struktured/Videos/drmario_sessions/rcr-obs-monitor-game-1751/`.
- Original recording: `20260918_173216_struktured_v6c_part2.mkv` in that parent.
- Exact AAC decode/stream-copy video: `build/obs-probe-{aac,video}-1757.*`.
- Audio, camera, branch diagnostics: `build/obs-probe-{audio-1760,camera-1761,branch-1762}/`.
- Handoff: full SNAC Yes screenshot `1756`, paused OSD-closed screenshot `1759`.
- Review `1763`: all 22 served artifacts fetched and hash-verified; six gap clips
  checked sample-for-sample against original native raw FL/FR. Encoded video and
  audio stream hashes match the original recording.
- Full unit suite: **946 tests pass**, including 13 new observer/review tests.

Next: instrument the recording-side buffering and monitor delivery after the
observed resampler, and reproduce the 32-sample shift with same-run PCM. Keep
capture-path attribution separate from the remaining SPC waveform and game
cadence work. No pop-free, perceptual-improvement or full-speed release claim.
