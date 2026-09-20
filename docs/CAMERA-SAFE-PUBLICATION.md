# Late camera publication: tearing prevented, timing still incomplete

Candidate `build/camera-safe-on-521/native-cpu.sfc`, SHA256
`43c8f5a8213844bb33624a3a980b67d14f39b9a8b0cc045560d7c66c330e3929`.
Default-off `experimental_camera_safe_publish`, based on hidden16/word-fill
candidate496. Disabled control521 is byte-identical to that parent. No Rival
deployment/restart; original-speed and complete scrolling/audio acceptance
remain unmet.

## Actual bug and change

The street's HDMA table has two entries: one fetched for line32, the other
for line159. The old camera hook overwrote both live entries whenever the
game completed its camera calculation. A completion between those fetches
could therefore draw the upper street with one camera and the bottom with
another. Stable-camera screenshots did not reliably detect this.

The new production helper reads the real nine-bit beam position inside the
existing interrupt-masked camera section. It permits the four table stores
before line30 (leaving margin before line32) or from line194 onward. Between
those limits, both live entries retain their previous generation. Original
F6/3D still contain the complete new camera; the next bounded VBlank publisher
uses them. No waiting, extra game tick, guessed camera, asset change or input
change is introduced. The existing retained-NMI path still executes normally.
The conservative194 cutoff covers the whole street, even after its final
HDMA fetch; further timing optimization must retain generation coherence.

This fixes tearing, **not late camera computation**. Delayed publication is
kept visible in the timing reports; the overall acceptance gate is not relaxed.

## Executed boundary and interrupt tests

- `camera-safe-oracle-530`: **42 actual beam-register cases**, covering
  early lines,29/30/31/32,38,158/159/160,193/194, VBlank and256/260, with two
  instruction offsets each. Checks complete committed/live camera values,
  neighboring table descriptors, X/Y/stack and completion before line32 for
  early copies. Five non-equivalent broken guards/copies are rejected.
- The first mutation run520 showed that ignoring bit8 alone is behaviorally
  equivalent for these NTSC high lines: their low bytes0–5 also permit copying.
  That was not falsely counted as a caught bug. Run522 instead rejects a
  forced high bit that incorrectly permits an active-street write.
  Fresh530 repeats the complete suite and additionally binds every negative
  ROM, RAM snapshot, receipt and mutated source into the report.
- `camera-safe-edge-524`: the extracted **complete production camera hook**
  passes11 fresh/already-acknowledged NMI edge cases plus8 visible-boundary
  cases, preserving A/P/X/Y/stack and committed state. Old-wait controls lose
  eight events; cleared-event and missing-ack controls are rejected. An
  initial test523 incorrectly expected a future NMI in a fixture that measures
  immediately before line200; the corrected expectation remains explicit.
- **488 Python tests pass.** Missing/duplicate renderer lines and unsupported
  selected states fail closed; a one-line split remains detectable.

## Full-route renderer test found the larger problem

`camera-parent-raster-527` and `camera-safe-raster-522` are independent complete
8,551-frame replays. Each matches its uninstrumented counterpart's entire
timeline and PCM. The observer cores are unchanged.

`audit_scroll_splits.py` selects frames solely from consecutive game-state
boundaries: active gameplay task, visible BG, no transition. It requires all
160 actual renderer lines32–191 in every selected frame; it does not select
only stationary cameras, fit images, or replace inconvenient samples.

| Measurement | Parent | Guarded |
| --- | ---: | ---: |
| Eligible gameplay frames | 7,235 | 7,234 |
| Frames with more than one street camera | **729** | **0** |
| Renderer lines checked | 1,157,600 | 1,157,440 |
| Frames differing from end-of-frame committed camera | 810 | 845 |

Reports: `camera-parent-split-audit-528`, `camera-safe-split-audit-525`.
The original known broken frame is also independently detected as a negative
control. Eligibility counts differ by one because execution timing changes;
no frames were rematched. At the7,234 shared frame numbers, first-street-line
scroll matches in7,172 and bottom-line scroll matches in6,471. This is not
proof of identical simulation/latency in every frame.

The810/845 comparisons use **end-of-frame** committed state, which may change
after drawing. They are retained evidence, not automatically810/845 missed
deadlines and not a claim that the guard adds exactly35 frames of delay.

At the original fixed failure, committed cameras remain202/204/204:

| Frame | Parent actual renderer | Guarded actual renderer |
| --- | --- | --- |
| 7556 | 200 on32–158;202 on159–191 | 200 throughout32–191 |
| 7557 | 202 throughout | 202 throughout |
| 7558 | 204 throughout | 204 throughout |

The guard eliminates the split without pretending that frame7556 draws the
already-late new camera. Unmodified primary images are on the review page.

## Remaining qualification

- Fixed input replay:9,409frames complete. Room loads remain **21/28/29**
  versus NES20/31/30; first room is still one frame late. First-visible
  offsets7/6/7 versus7/7/7; room2's earlier fade still fails fixed-offset
  image timing. Entry report525 is not promoted to a pass.
- Background audit524: **785 exact** stable playfield samples, coverage
  259/103/110/313. The unchanged gate nevertheless fails821 frame-end table
  publication warnings and11 settling samples. Many warnings now explicitly
  reflect a retained live generation; they are not waived or rewritten.
- Both Present Status entries in status-audit526 match exactly.
- SPC-provenance526 verifies **9,233 complete packets**, all bound CPU-write,
  header, key-on and synthesis-ready checks, and full normal/observed PCM
  equality. Processing161–1208SPC ticks. No acoustic/physical fidelity claim.
- Park-audit526 has no stable packet interval above1.5frames. Neutral528
  has no late NMI intervals in the observed7600–8420 window. Neither implies
  whole-game speed/endurance acceptance.

Next: bring the camera calculation/publication before the street deadline
while retaining this anti-tearing safety rule, close the remaining first-room
frame, and continue physical/perceptual audio diagnosis. A tear-free but late
frame is not substituted for original-speed success.

Review: `http://127.0.0.1:8766/camera-safe-review-529/`.
