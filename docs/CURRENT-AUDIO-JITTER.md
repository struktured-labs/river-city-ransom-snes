# Current full-route audio and the line-56 camera collision

Broader qualified candidate: 3819, SHA256
`aaa09580b6aaa8201e022089ccf91e3d51d35d32f15869961a1c73fec9ecec88`.
No hardware deployment or acoustic approval.

## Fresh full-route audio self-test

Capture 3840 preserves the full 9,090-frame primary timeline and native PCM of
3824. Audit 3841 validates actual received packets, raw-DAC/native PCM identity,
note-start pitch/volume ordering, and original main-loop events.

- 8,641 sound packets and 1,588 restart events pass the startup checks.
- 4,846,034 native stereo sample frames, peak 6,307, no clipped samples.
- Largest adjacent sample step: 4,329. A waveform edge alone is not a pop verdict.
- Four stable-room cadence populations: 598 / 1,746 / 477 / 847 intervals,
  all two frames. Busy frames are not excluded by the classifier; none occur
  in those eligible populations. This is not matched-NES heavy-combat evidence.
- 7,342 stable completed-packet intervals: 10.097–23.054 ms, median 16.643 ms.
  All 1,298 excluded intervals remain in JSON. Longest is frames 7160–7161,
  packets 6726–6727, room 2.

[Full-route native audio and measurements](http://127.0.0.1:8766/camera-edge-route-audio-review-3841/).
Report computation took 46.905 seconds, separately from replay.

## Short replay tradeoff retained

The 3819 combat-edge recovery fixes the prior missing call but does not improve
every interval. Relative to 3800, the short prefix's maximum completion gap
increases from 22.159 to 22.325 ms. Local driver-return maximum increases from
21.975 to 22.406 ms. The earlier frame2120 target remains improved at 18.680 ms.
All ten changed pictures and untouched native clips remain in
[comparison3839](http://127.0.0.1:8766/camera-edge-audio-review-3839/).

The largest short-prefix gap is packets 1813–1814, frames 2205–2206. Fresh
instruction observation 3842 is neutral against the same-core 2,579-frame
control. At frame2206:

- Camera boundary enters at line55/cycle604, masks at55/1042.
- Eligibility beam sample is56; `CPX #60` rejects early sound service.
- Camera/retained work continues through the nominal line80 timer interrupt.
- The sound driver finally starts at161/392 and returns at181/400.

This establishes a scheduling delay before the driver, not a synthesis fault.
The trace is bound in `build/camera-edge-jitter-instructions-3842/capture.json`.

## Isolated eligibility experiment

3843 changes only the existing lower eligibility comparison from60 to48 in
eight game banks (plus checksum), preserving ownership checks and the line240
upper bound. It services only an already-pending tick; no duplicate packet or
new timer event is manufactured.

ROM SHA256 `7f65ee3ac50936bd6a6f9aefcfd8b9c00c02638a1f784bc77a7e7888e13dd90c`.
Prefix3844 has no faults, identical counter/input trajectories, and unchanged
target HUD pictures2473/2485; ten other picture differences remain. Finalized
audio observation3845 is neutral, with replay8.406s / total8.996s including
process finalization. Qualification of this trial is separate from3819.

The short trial improves measured stable packet spacing from11.190–22.325 ms
to12.541–20.281 ms. Local original-driver return intervals improve from
11.554–22.406 ms to13.073–19.909 ms. Both observations contain2,179 completed
packets and no clipped samples. The ten picture changes are retained, not
waived by the better timing. [Native clips and every changed picture](http://127.0.0.1:8766/audio-boundary48-review-3846/).

No claim of pop-free sound or NES waveform equivalence follows from the narrower
interval range. Subsequent qualification below belongs to this exact ROM.

## Broader graphics and combat qualification of 3843

Ordinary capture3847 completes9,090 frames. Same-core observer/control pairs
3851/3855 and3852/3856 preserve their complete primary timelines and native PCM.

- [DMA audit3857](http://127.0.0.1:8766/audio-boundary48-dma-review-3857/):
  52,135 general transfers, no unsafe envelopes;1,939 forced-blank,
  50,192 VBlank and4 other classified transfers. This excludes HDMA and does not
  prove graphics-publication freshness.
- [Renderer audit3858](http://127.0.0.1:8766/audio-boundary48-renderer-review-3858/):
  7,473 eligible frames,6,502 held frames checked; no coverage, split or stale
  camera failures.
- [Combat audit3854](http://127.0.0.1:8766/audio-boundary48-combat-review-3854/):
  each policy completes4,930 frames with neutral observation and no faults.
  Stable sustained attacks:1,752 two-frame intervals; running/jumping:1,709.
  No off-cadence intervals in either eligible population; busy frames remain
  included. These are not matched-NES encounters or a full-game speed proof.

The [strict palette comparison3853](http://127.0.0.1:8766/audio-boundary48-palette-review-3853/)
does **not** pass:20 differences at frame2429 have changed source/preparation
stages and therefore cannot be classified as earlier/later publication of the
same source. The raw records show an earlier fade step, not permission to waive
the gate. Original timing and broader palette behavior remain unresolved.
The eleven previously observed earlier-publication differences are also retained.

Present Status qualification still belongs to3819, not3843. No hardware
deployment, release promotion or acoustic acceptance has occurred.

## Full-route audio rejects a blanket improvement claim

Fresh observation3859 preserves every primary frame and native sample of3847.
[Audit3860 and native PCM](http://127.0.0.1:8766/audio-boundary48-route-audio-review-3860/)
retain8,641 completed packets,1,588 restart events and4,846,034 stereo sample
frames. Startup checks pass; no clipping. Peak6,368; largest adjacent step4,554.
Neither measure establishes that popping is fixed.

Stable packet gaps are9.944–23.171ms (median16.633), versus the parent's
10.097–23.054ms. All7,342 stable and1,298 excluded intervals remain in JSON.
The longest current gap occurs at frames7114–7115, packets6680–6681, during
`park_entry` (room2). Thus the better short prefix does not improve the
full-route worst case. Report analysis took44.693seconds separately from capture.
The four stable-room game-loop populations remain598/1746/477/847 intervals,
all two frames. The next diagnostic targets the exact park-entry service delay;
this result does not authorize promotion or a pop-free claim.

## Park-entry recovery trial3862

ROM SHA256 `f68651c81acebf023e3def93c299a73b4db94cee47c18de99d292d38c94e9b10`.
`tools/build_audio_boundary32.py` changes only the eight lower-cutoff immediates
from48 to32 plus checksum, on exact3843. Pending/depth/mapper/NMI guards and the
line240 upper limit remain unchanged. Seven tests cover the patched compare/
branch bytes, all262 beam positions, old line40 rejection, changed-byte rejection,
checksum/limited diff and the earlier camera-edge wait helper.

Neutral instruction replay3861 establishes the park collision at frame7115:
camera enters39/912, eligibility samples40, so the line48 gate rejects service.
Original sound enters154/1190 and returns180/1054. In trial3865 it enters42/288
and returns68/162. The consecutive driver-return gaps change from
22.138/10.881ms to14.984/18.035ms. These are CPU driver-return intervals, not the
SPC packet-completion timestamps quoted above. The ordinary target scene is
the harness's `park_entry` phase; this is not a match to the user's OBS encounter.

[Handoff comparison3867](http://127.0.0.1:8766/park-audio-handoff-review-3867/)
contains the exact events, all23 changed route pictures, and untouched native
117–121s audio clips. All9,090 counter/input/camera frame samples match3843.
Observed trace replays took34.085s for the parent and27.296s for the trial;
same-core full primary timeline/native PCM neutrality holds separately for each.

[Full audio audit3866](http://127.0.0.1:8766/audio-boundary32-route-audio-review-3866/)
on fresh3864 narrows stable packet spacing from9.944–23.171 to12.171–20.991ms.
All7,342 stable and1,298 excluded intervals remain; both builds have8,641 packets,
1,588 restarts and4,846,034 native stereo samples. Current peak6,769,
max adjacent step4,504, zero clipping. Original stable-room cadence populations
are unchanged, all two frames. Analysis33.803s, separately from replay.
Worst remaining packet gap:8531–8532, room3. No pop-free verdict.

### Graphics tradeoff: one visible dialogue glyph is later

Neutral direct-memory captures3868/3869 observe84 frames across the existing
dialogue/HUD windows. [Audit3870](http://127.0.0.1:8766/park-text-tradeoff-3870/report.json)
preserves all records and rejects the no-regression gate: one earlier text tile,
one later tile, and two unsupported playfield tile differences. Original
nametable sources match in every sampled frame. At5989 the source and prepared
row25/column11 both contain tileEB in both builds, but the trial's VRAM still
contains00. The previous star at5982 instead arrives earlier in the trial.

Fresh neutral CPU traces3871/3872 locate the late letter's cause at5988:
parent consumer cursor25 publishes the visible row first. Trial cursor26 finds
mirror row89 first, then searches90..127 and0..25. That search takes3,314 master
clocks; the visible row's beam check reaches252/128 and rejects at the unchanged
line252 deadline. Both rows were already prepared at5988. The visible row reaches
VRAM at5990, one frame later than the parent. Do not waive this as better audio.

Next: reduce the bounded row-search cost or otherwise prove timely publication
without relaxing transfer safety, changing original graphics, or hiding mirror
updates. Broader DMA/renderer/palette/combat qualification of3862 remains pending;
3843's results cannot qualify this cartridge. Neither build is promoted.
