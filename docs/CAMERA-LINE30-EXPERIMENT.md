# One additional camera-publication scanline: unpromoted experiment

Rival remains on branded616 (`34835f8`), paused with SNAC restored. No hardware
input, cartridge change, restart or OBS change in this investigation.

The previous hardware-audio turn was progress: it established real gameplay
audio and a silent paused interval, but did not establish pop-free gameplay.
This turn investigates the remaining camera-publication warnings directly.

## What the warnings actually mean

The old sweep's large settling counts can span a departure and later revisit
to the same camera value. They are not measured image-settling delays. Existing
failed sweep reports and their gates are retained, not relabeled as passes.

For the exact deployed ROM, the existing neutral CPU trace places833 of834
frame-end/rendered-camera mismatches at camera-tail entries after line30. The
remaining entry starts at line29/cycle1322, close enough to the boundary for
the guard to latch line30. End-of-frame RAM is not necessarily what existed
before scanout. Entry timing is not itself the completed store/latch time.

## Candidate and safety checks

New default-off `experimental_camera_line30` requires safe camera publication.
It changes only the early cutoff from `<30` to `<31`; the late cutoff194 and
four camera-table stores are unchanged. There is still a full scanline after
the latest eligible latch before the line32 street fetch.

Candidate646 is byte-identical to initial test638:
`0236711a97060f1acffe306ec7c385b71374c5865a312d11b3ecae55c69ad531`.
The disabled646 control is byte-identical to unbranded parent608. Relative
to608, only eight mirrored immediate operands and checksum bytes change.
No original graphics, sound engine or controller mapping is changed.

`camera-line30-oracle-645` executes123 cartridges: the existing beam matrix,
75 additional real-cycle delay cases around29/30/31, and six default-disabled
controls. The fixture reads the helper's actual latched beam without relatching,
so a delay crossing a line does not falsify the expected result. All26 enabled
cases actually latching30 complete the copy and caller checks before32.
Six executed mutants reject late/early limits, the old cutoff, a forced high
vertical bit, wrong second low-byte store and missing high-byte copy.

## Full route: mixed benefit, no promotion

Fresh normal/CPU/renderer/background captures complete8,629 frames. Each
observer's complete timeline and PCM match its own normal-core control.
The candidate's PCM and timing differ from the parent; no cross-ROM waveform
equivalence is claimed.

- Zero splits across7,315 eligible frames /1,170,400 street lines (`splits640`).
- Zero stale holds across6,385 unchanged committed-camera frames (`held640`);
  the known old missed-copy failure still fails.
- All780 selected background positions exact, coverage259/103/110/308
  (`background-audit644`). Original publication/settling gates still fail.
- Room visibility is no later than NES; the existing room2 fade mismatch
  remains6 versus7 frames after rendering enable (`entry642`).
- Actual park camera-call intervals average1.99950/2.00029 nominal frames;
  maxima2.34926/2.29410 (`cadence-audit642`). Encounters differ from NES, so
  these are not a matched-combat speed certificate.

The full-warning classifier compares unbranded parent608 with candidate638,
using neutral CPU-entry and all-line renderer captures. Parent has839 frame-end
warnings; candidate821. Of these, entries before31 fall from13 to2. The two
remaining early entries occur at line30/cycles1320 and1346, near the guard's
boundary. This diagnostic does not declare the warnings missed deadlines.

Crucially, frame2531 improves (committed65: old displays63, candidate65), but
frame1440 goes the other way (committed50: old displays50, candidate48). Its
camera entry shifts from line27/cycle424 to line31/cycle628. Both complete
frames are shown in the review; no favorable-frame-only promotion.

Next: compare actual displayed-camera cadence and producer timing against the
NES through the full route. A looser safe cutoff alone does not guarantee
smoother scrolling. Keep this experiment off until the net latency/jitter
benefit and full audio/status/shop regressions are established.

An initial background capture640 used the wrong observer binary. The oracle
rejected it; no check was relaxed. Capture643 uses the qualified window-aware
core and is the source of background audit644.

Review: <http://127.0.0.1:8766/camera-line30-review-647/>.

534 Python tests pass; `git diff --check` is clean. The final beam-oracle
sources and all executed artifacts, review source/image hashes and published
review links were rechecked. No speed/audio release gate was waived.
