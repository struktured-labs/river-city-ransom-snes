# 21-frame loading experiment: real scrolling regression, not promoted

Candidate `build/hidden16-word-496/native-cpu.sfc`, SHA256
`2546b740c9d58370188a9a60e85cdf1c14a4bee54333788bec6b2c8bd0d962f3`.
It combines the existing paired-read candidate 451 with 16 hidden rows and
the existing word-fill option. No new production assembly/default change.
No Rival restart. Original-speed requirement remains unmet.

## Loading: a scoped one-frame improvement

Fixed replay `hidden16-word-497` completes 9,409 frames. Entry audit 498:

| Measurement | Current baseline 451 | Experiment | NES |
| --- | --- | --- | --- |
| Room-change to visible, rooms 1/2/3 | 22 / 30 / 29 | **21 / 28 / 29** | 20 / 31 / 30 |
| First visible offset after enable | 8 / 7 / 7 | 7 / 6 / 7 | 7 / 7 / 7 |

Room 1 and room 3 match all 40 fixed-offset background images. Room 2's
fade steps appear one frame earlier (differences at offsets 6/10/14/18),
so the unchanged fixed-offset exactness gate fails. This is not silently
reclassified as a pass. Absolute first-room visibility is frame 2131 versus
baseline 2126: pre-entry timing also changes. The 21-frame room-load duration
is **not an overall faster-startup claim**.

Separate 15-row experiment `hidden15-496`, SHA256
`c7f0fcffa8b5de5f7d4f458e518623c105c8029c75bba7e8be699cd637247d72`,
completes 9,408 frames and remains 22/30/29, first visibility 8/7/7. No gain.

## Fresh qualification of this exact combination

- Adaptive observed/normal captures 499 both complete 8,551 frames, identical
  full primary timeline and PCM. Background audit 500 compares **784 exact
  full-playfield background positions**, coverage **259/103/110/312**.
- That audit nevertheless fails: late publication at frame **7557**, room 3,
  expected camera204 but published202; nine settling failures remain. Long
  settling values have not been independently explained for this candidate.
- Both Present Status entries in `hidden16-word-status-audit-500` pass with
  zero tested-region pixel differences (2,235-frame capture).
- `hidden16-word-park-audit-500` has no stable-park packet gap above 1.5 frames.
  `hidden16-word-neutral-500` confirms full 9,409-frame timeline/PCM equivalence
  and zero late NMI intervals in the observed 7600–8420 window. That window
  **does not include** the earlier scrolling failure, and is not a whole-game
  speed or sound-fidelity pass. No new complete bus/key-on proof is claimed.

## Actual renderer confirms the scroll problem

Neutral full-route raster capture `hidden16-word-raster-501` observes all
160 playfield lines at the original flagged frame and adjacent frames.
`hidden16-word-late-lines-502` retains the unshifted primary images:

| Frame | End-of-frame committed / published | Actual renderer |
| --- | --- | --- |
| 7556 | 202 / 202 | camera200 on lines32–158; camera202 on159–191 |
| 7557 | 204 / 202 | camera202 on all lines32–191 |
| 7558 | 204 / 204 | camera204 on all lines32–191 |

This is a real split followed by a lagged displayed camera, not just the
earlier interrupted-working-camera measurement artifact. Do not inherit
candidate451's explanation or waive this failure because sampled stable
backgrounds match. The first audit invocation rejected the added background
telemetry field; the corrected verifier excludes only that independently
bound plane, retaining exact game-state/PCM equality. Tests reject changed
game state disguised as background telemetry.

`hidden16-word-late-cpu-503` traces frames7555–7558 on the complete adaptive
route. Its camera hook arrives at frame7556 **line38, cycle710**, after the
line32 playfield begins; the next hook is frame7557 line239. This gives a
concrete pre-camera deadline target for further CPU work. End-of-frame
committed state alone is not treated as proof of when that value was ready.

`hidden16-word-camera-cost-504` verifies the complete CPU-observed timeline
and PCM against the normal route. NMI-to-sound-driver costs15,082 master
clocks; driver13,536; restore-to-sender1,136; sender-to-camera52,714. The last
interval includes transfer, interrupt return and remaining game work, not
just audio cost. This is the next interval to break down before changing code.

481 Python tests pass; no candidate promotion. Review:
`http://127.0.0.1:8766/publication-and-load-review-505/`.
