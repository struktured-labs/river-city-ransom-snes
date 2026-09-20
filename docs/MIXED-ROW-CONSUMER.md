# Mixed-group row consumption experiment

Candidate3583: `build/consumer-mixed-game-3583/native-cpu.sfc`, SHA256
`f56ab5f1df86762993c584821461e3197a96913ddb1f54175f27d66d4db33515`.
Experimental only. No default change, MiSTer restart, OBS action, or deployment.

## Change and causal evidence

The authenticated3527 instruction replay showed the consumer spending enough
time searching empty entries after a transfer to miss the next ready row's
admission deadline. Producer grouping3556 did not improve the health delay;
raising the row cutoff to250/251 also left it at five frames. Those experiments
remain separate, with no broad campaign triggered by their non-improvement.

`snes/consumer_mixed_scan.asm` keeps the existing eight-entry OR reduction for
empty groups. For a mixed group it locates the first ready flag word directly,
instead of repeating the entire group search after each scalar miss. It keeps
the same queue order and visit budget, never crosses the128-entry array, and
does not add persistent state, change priority, or touch original graphics.
CHR246, row249, palette254 deadlines, early OAM and the SPC engine are unchanged.
The103-byte helper is a guarded patch on exact3527, not a relink of the dirty tree.

## Short replay results

The same original health source changes at8242. In3527 it reaches VRAM at8247;
3583 reaches VRAM at8245: **five → three frames**. The32-frame health and50-frame
dialogue replays retain identical initial full CPU/WRAM/VRAM and matched original
source events. All playfield pixels, sprite source/staging, sampled game/NMI
counters, cameras and delivered inputs match the authenticated control.

All11 dialogue glyphs publish within2–3frames. Individual glyph latencies differ
from3527; this is an unchanged latency envelope, not identical per-glyph timing.
Full cross-ROM register/RAM/audio differences remain in the reports. These
checks are not original-NES speed or acoustic-fidelity equivalence.

Each short replay took about6.1seconds including baseline verification. Fresh
boot through right_08 completes2577frames in6.67seconds. The full route completes
9089frames. Further results are recorded by `tools/review_consumer_mixed_scan.py`
and must be inspected, not inferred from these short passes.

## Important retained failures and stronger integration tests

- 3559,3569 and3573 jumped to$83D9, inside the operand of the original
  `LDA $1D00,X` at$83D7. Their apparent speed/latency gains are **invalid
  optimization evidence**. The game replay caught failures that the abstract
  queue oracle missed. An earlier odd-cursor/performance explanation for these
  failures was incomplete; the wrong instruction boundary is established by
  neutral instruction tracing and actual ROM bytes.
- 3573's dialogue replay retains11 unrendered/right-censored source generations;
  none was silently excluded.3559/3569 also retain failed ordinary boots.
- 3579 fixes the continuation and meets the three-frame health target but still
  fails the settings transition. Its all-empty search remains a timing suspect,
  not an independently traced root cause.3583 restores the fast empty-group path
  and passes the boot replay.
- New tests execute emitted helper bytes and authenticate their continuation
  against the real pinned cartridge. The actual bad3573 helper fails the
  instruction-boundary gate. Exhaustive empty ring/budget and every-single-ready
  cursor cases plus randomized mixed/partial budgets compare to a scalar oracle.

## Qualification captured for3583

- Full general-DMA observer/control:9089frames with identical primary timeline
  and native PCM;53051 completed envelopes pass, latest visible end259. HDMA and
  physical per-byte timing are outside this observer.
- Actual renderer observer/control:9089frames,7477eligible frames, zero missing
  coverage, splits or stale-camera failures.
- Sprite cohort:21known generations through2020 render next frame, observed
  through2024; later/censored sources remain in the evidence.
- Raw first-room WRAM/VRAM snapshots2390–2450 are observer-neutral through the
  2577-frame prefix; actual source-byte equality and full-route pending-job
  liveness are separately audited, not inferred from safe completed DMA.
- Full-route audio/DSP capture is observer-neutral. Native32040Hz stereo PCM is
  retained. Startup timing/volume checks and waveform statistics are separate
  from hearing, acoustic fidelity, or a pop-free verdict.
- 1420 unit tests pass in20.922seconds (`/tmp/rcr-tests-3600.log`).

[Compact browser collage and native audio](http://127.0.0.1:8766/consumer-mixed-published-3602/)
links the [complete audit](http://127.0.0.1:8766/consumer-mixed-review-3601/report.json).
All17 listed scoped gates pass; release_ready and physical_verified remain false.
All1383 source bindings and six detailed-report artifacts were revalidated. Both
web pages were browser-rendered and visually inspected. The WAV is byte-identical
to the full-route capture (SHA256
`6d69e9ea460aba7987683e3dbdc2fd0c02d0e515bc46fa5b1f266640f7816093`)
and serves with HTTP200; neither this nor the image inspection is a hearing claim.

The two CHR jobs originate at2423 and actually match original source bytes at
2425/2426. Longest visible pending span remains3frames. Audio checks cover8641
commands,1585restarts and64 startup phases with no tested startup pitch/volume
failure.4,845,501 stereo samples have peak7019, maximum adjacent step4842 and no
clipping. The adjacent-step maximum is larger than3527's4361; these values alone
do not establish a pop regression or improvement.3668 measured stable game-loop
intervals remain2frames. Original-NES matched speed is still not established.

Report generation took40.93seconds; captures and source verification dominate
the broad audit. Exact-state trials remain about6seconds. The short-loop skill
kept failed variants out of that broad campaign and made the real bad entry an
explicit negative control rather than a hidden discarded artifact.

Large raw evidence remains in `build/overflow-3526` on the data volume. The
review exports only selected images, JSON/HTML and byte-identical native WAV
into the restricted web root; ROMs, states and raw RAM are not published.

Still required before release: current menus, both-direction scrolling routes,
matched original-game workloads, controller combinations, and physical/acoustic
acceptance. The complete speed/scrolling/audio goal remains active.
