# Rival 071c89e: gameplay, pause, scenery, and reference-silence follow-up

September 18, 2026. No new ROM change or restart in this follow-up. The previous
goal turn made progress by deploying the integrated triangle anti-click build;
this turn adds physical gameplay evidence and a new source-bound diagnostic.
The speed, scrolling, and audio goal remains incomplete.

## Physical episode

Rival was at the 1P menu with SNAC Yes. The harness temporarily set runtime SNAC
No, used the existing idle USB pad to start the game and perform street combat,
then restored **SNAC Yes**. Final screenshot950 shows the game paused outside
Cross-Town High School, OSD closed. Saved SNES.CFG stayed
`066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
No physical SNAC-button consumption claim.

OBS recording/replay began stopped. Two owned 30-second recordings were started
and stopped; gain, mute, scene and monitoring were unchanged. The first recording
ended before the requested pause and is retained as lead/combat evidence937/939.
The second captures pause→resume→street combat/movement→pause. Video941 is an
unaltered stream-copy remux; its audio is decoded to stereo48kHz PCM16 without
gain changes. Both original MKVs are retained. OBS is stopped again.

The same-recording pause pair954 checks gameplay seconds5–15 against pause
seconds19–29. Gameplay RMS445.78, peak2,306, largest adjacent step874; no clipping.
The ten-second paused clip contains **zero nonzero samples**. Replacing gameplay
with silence or inserting one paused click is correctly rejected. This establishes
the sampled digital silence, not analog silence or pop-free gameplay.

There are three long unclassified combat silences:

| Recording start | Duration |
| --- | --- |
| 9.099521 s | 147.188 ms |
| 9.378833 s | 151.438 ms |
| 13.491667 s | 147.146 ms |

The street stays visible; these are not obvious scene-loading blackouts. All six
active-window gaps≥10ms and the eight strongest separated steps are retained in
report948. Whole-episode report955 also retains pause/transition intervals.
Codec/resampling and uncalibrated input/capture latency prevent sample-exact
game-event attribution. These events are not dismissed as musical rests.

## Scenery cadence and exact-frame context

Report946 measures every one of1,792 decoded video frames, using the existing
fixed skyline ROI x340/y160/w1280/h120 and256 logical pixels. It accepts1,786 of
1,791 pairs; five rejected pairs remain. Equal-signed camera-step intervals are
119×2 frames,4×14,1×4,1×6,1×1. The two short irregular cases are:

- Frames656→660, four-frame spacing between −1-pixel camera changes. Frame658
  shows Alex higher in his jump while scenery remains stationary. This is not
  a full-game freeze; it does not by itself prove correct camera behavior.
- Frames992→993, one-frame spacing between +2-pixel camera changes. Both scenery
  and actors advance. Capture cadence versus game timing remains unresolved.

OBS output is60fps; the DeckLink input is Auto. We do not infer a hardware input
refresh rate from that setting. All PNGs are exact decoded frame selections;
the review uses HTML collages, not altered game imagery. One-based frame numbers
are explicit. The three long audio gaps have before/during/after screen context.

## Stronger silence-reference harness

`audit_silence_reference.py` complements the constant-held-voice check. A fresh
asset-free NES player executes all38,334 ordered APU writes captured on emulator
route892, scheduled at actual SPC publication frames. All8,934 source frames,
register shadows and write counts pass. Missing writes, missing empty frames,
and a missing bank switch are rejected by the existing replay controls.

For every measured SNES exact-zero gap, the new diagnostic retains NES callback
energies at the same source frames. One callback at each edge is excluded;
three consecutive interior callbacks with AC RMS>32 in both NES channels flag
sustained reference activity. There is no gain, phase, time or sample-rate fit.
Native rates remain SNES32,040Hz and NES48,000Hz. Thresholds are declared, not
selected to optimize this recording.

Report957:310 gaps have guarded interiors, covering1,003 callback frames. There
are257 active NES interior callbacks:255 gaps have one, one gap has two, and
none have three consecutive. These short discrepancies remain visible; this is
**not an exact synthesis-fidelity pass**. Four injected five-callback dropouts
(menu, idle, shop, park) are caught. Seven unit tests cover silent/DC/dead-channel
references, boundary guards, short gaps, missing/reordered callbacks, thresholds,
and a five-callback dropout. **673 tests and `git diff --check` pass.**

This replay uses emulator-captured commands, not a hardware APU trace. It cannot
classify the three physical combat gaps above. Preliminary report956 is retained
but predates the final control additions; use source-bound957 for current results.
An initial replay invocation used the normal capture without a bus-trace receipt
and failed before output creation; replay952 uses the verified neutral observer.

## Next work

Review960 retains native-rate NES/SNES audio for frames6560–6605, deliberately
centered on the largest short discrepancy (frame6580, NES AC RMS3,007.67).
SNES callbacks6579/6580/6600 are exactly silent; no NES callback is exactly zero
in that window. Packet6580 starts new audible values, while preceding packets
mute the voices. Callback/publication phase, APU behavior and filter decay need
separating before attributing this to an omitted or delayed note.

Correlate physical combat gaps with reproducible game audio cues/commands and
test shorter onset/offset discrepancies. Resolve capture versus game timing for
the one-frame scenery event; keep broader original-speed, input-latency, strict
publication, and full-game validation open. Splash and controller presets were
not changed by this follow-up.

Review: <http://127.0.0.1:8766/triangle-game-followup-review-958/>.
