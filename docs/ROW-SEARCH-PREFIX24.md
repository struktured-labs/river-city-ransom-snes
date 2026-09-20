# Bounded row-search optimization after the park audio fix

No promotion, deployment, or release verdict. The speed/scrolling/audio goal
remains open. All original graphics, queue order, visit budgets, and admission
deadlines are preserved by this experiment.

## Implemented and checked

`snes/consumer_prefix24.asm` uses twelve absolute word probes for the first24
flags when a bounded search begins at zero with at least24 visits remaining.
Other searches retain the suffix/mixed-group paths. It adds no persistent state
and never reads beyond the queue or remaining visit budget on this new path.
The helper occupies verified free C04000 space; its continuation remains the
authenticated scalar instruction at C083D7, not the old erroneous C083D9.

Candidate3873 SHA256:
`744c5f723cd8bf3826b255a1f4aaba2b46d541ccf43f5496a30c7296aa2da11a`.
Candidate3883 removes the extra trampoline from both existing call sites
(C077C9/C0839E), leaving the helper unchanged. SHA256:
`e269de592e045130e8e0478acd1728b51200d6144834b95bdf868f5a5f5ebc9b`.
Both are exact-parent guarded patches, not relinks of the dirty worktree.

Five machine-code tests exercise every empty-ring cursor/budget, every single
ready-row location, randomized mixed/partial queues, the historical bad
continuation, and bounded-prefix reads. The combined16-test scanner/audio-edge
suite passes in3.693seconds; the new scanner tests alone took2.051seconds.

## The targeted glyph is genuinely recovered

Neutral instruction observations3872/3876 show the same search starting with
cursor90 and64 visits at frame5988. Including the new trampoline, search time
falls from3,314 to2,870 master clocks. The visible row25 admission check moves
from line252/cycle128 to251/1058 and passes the unchanged line252 cutoff.

Frame5989 now displays the prepared tileEB at dialogue row25/column11. Source,
staged bytes and actual VRAM agree; the real failed3862 remains the negative.
The mirrored row is still transferred first; no priority or alias suppression
was introduced. Neutral direct-memory observations cover84 sampled frames over
the full9,090-frame replay.

## Remaining publication failure is explicit

Both optimized variants miss tileE8 at row25/column12 on frame5991. Original
sources and prepared values agree with3843, but actual VRAM is still00. At5990,
the3873 cursor now starts26, so mirror HUD66 and mirror dialogue89 precede the
visible row. The post-transfer cutoff ends the pass at line252 before it can
return to that row. Recovering the previous glyph changed where the ring starts;
it did not provide enough overall transfer capacity for the next combination.

The strict84-frame comparison to3843 reports two earlier text words, one later
text word and two unsupported playfield word differences; original nametable
sources agree throughout. Its no-publication-regression gate remains false.
[Direct-variant audit3886](http://127.0.0.1:8766/consumer-prefix24-direct-text-review-3886/report.json).

Next investigate overall queue search/capacity when HUD, dialogue and their
mirrors are ready together—not a per-letter exception, a relaxed cutoff or
silent alias starvation. Broader palette, renderer, sprite and combat coverage
must still be repeated for the selected final cartridge.

## Qualification belongs to each exact variant

3873 ordinary replay preserves every original game-counter, input and camera
sample of3862;83 picture changes remain, not waived. Its neutral audio3877/
[audit3880](http://127.0.0.1:8766/consumer-prefix24-audio-review-3880/) retains
8,641 packets,1,588 restarts and4,846,034 native stereo samples, no clipping.
Stable packet gaps12.351–20.933ms; all7,342 stable and1,298 excluded intervals
remain. Four stable-room cadence populations are unchanged and all two frames.
This does not establish pop-free audio or matched-NES speed.

3873's [DMA audit3882](http://127.0.0.1:8766/consumer-prefix24-dma-review-3882/)
passes52,624 CPU general transfers (50,694 VBlank,1,926 forced blank,4 other),
latest visible end259. Same-core whole-timeline/native PCM neutrality holds.
HDMA and physical per-byte behavior are outside this safety check. This result
does not qualify3883 or imply publication freshness.

3883 has its own neutral full audio capture3888 and
[audit3889](http://127.0.0.1:8766/consumer-prefix24-direct-audio-review-3889/):
the same8,641 packets/1,588 restarts, stable12.351–20.933ms packet range, no
clipping and unchanged two-frame room-cadence populations. Peak6,445;
largest adjacent step4,406. Analysis43.304s, separately from capture.

[Direct-variant comparison3887](http://127.0.0.1:8766/row-search-direct-review-3887/)
retains all63 changed pictures versus3862 and untouched96–102s native clips.
Every original game-counter, requested/delivered input and logical-camera sample
matches across9,090 frames. The two raw text deadlines show the tradeoff plainly:
5989 changes from missing to current;5991 changes from current to missing.
The neutral direct-memory capture took37.815s versus47.076s for the reused3862
capture; these are individual observed runs, not a controlled speedup benchmark.
No broader graphics or physical-console qualification is claimed for3883.
