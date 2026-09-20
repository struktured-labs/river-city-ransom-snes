# Actual sound-driver timer phase experiment

Candidate3665: `build/audio-phase-bank-game-3665/native-cpu.sfc`, SHA256
`66b6d8d24316f8f71d699fa1eb1fc549d98a31c1a6c1907534468289fb5fe98b`.
This is experimental, not deployed or promoted. The latest qualified parent
remains3631. No MiSTer, OBS or controller action was taken.

[Exact clocks and native audio links](http://127.0.0.1:8766/audio-phase-review-3670/).
The page was rendered and inspected; its linked native candidate WAV returned
HTTP200. No samples were normalized, retimed, aligned or resampled.

## Implementation and retained failures

The tested isolated recovery mechanism now calls the real original sound driver
at vertical timer line80. Deferred jobs have their own pending flag and native
NMI identity. Existing completed-audio tokens are never fabricated for queued
work. Guarded enable-policy sites recover a missed timer before releasing their
critical section; old jobs can fall back on a later NMI. The ordinary and
coroutine return paths keep separate stack ownership. IRQ returns reenter the
original RTI in the tracked game bank, since emulation RTI does not restore PB.

1.3661 (`28248a3a…`) moved driver calls but added recovery overhead before the
bounded publisher. Capture3662 stopped at settings,2941 frames, incomplete.
No scheduled audio jobs existed at that failure; it was a graphics deadline
regression, not evidence of better sound.
2.3663 (`1899551c…`) adds a cheap no-pending enable path and moves ordinary
fallback after publication. It reached gameplay but capture3664 failed with
an adapter fault,3195 frames, incomplete. The isolated probe's DB=0 setup was
inappropriate for the real driver's banked reads.
3.3665 preserves the interrupted game data bank. DP/context preservation remains;
only the four-byte DB-zero sequence in each scheduler wrapper is replaced by
NOPs. Capture3666 completes2537 pause/status frames with no adapter faults.

The source-bound build chain is `build_audio_phase_trial` →
`build_audio_phase_fast` → `build_audio_phase_bank`. Historical helper binaries
in copied candidate folders are not all current; the final ROM plus recorded
patch manifests are authoritative. Parent hashes, exact opcode contexts and
replicated helper space are guarded. Two failed builds/captures are retained.

## Actual output improvement

| Measurement | Parent3631 | Trial3665 | Original NES |
| --- | --- | --- | --- |
| Request → driver |12.841ms|2.752ms|2.415ms|
| Separated pause sound onset |58 input-relative frames|57|57|
| Original ordered sound-register writes |7|Same7|7|

Neutral instruction/DSP observer3668 reproduces all2537 primary timeline frames
and native PCM from3666 exactly. Its1430–1445 instruction window contains one
driver entry in every frame, all at line80. The measured request occurs at
1437 line37 cycle508; driver entry line80 cycle962; return line93 cycle900.
The source command sequence is4004=F0,4004=F0,4005=08,4006=A2,4006=A2,4007=00,
4004=FF, exactly matching the authenticated original NES call. This is not an
assertion of complete waveform equivalence or original-game speed.

Onset audit3667 rejects an inserted two-frame delay and dead audio. Present
Status audit3669 passes actual numeric tiles and fixed-region pixels on opening
and reopening. Baseline scenario3671 completes2243 frames: despite the folder
name `audio-phase-full-3671`, this is only the baseline scenario, NOT the park
traversal. The actual longer scenario is3672, `traversal-park-single-sweep`;
inspect its receipt/results separately before claiming it passed.

Fresh3672 now completes9090 frames, no adapter faults and no requested/delivered
input mismatches. Final counters show7452 scheduled/7452 serviced, pending0 and
fallback0. Native32040Hz PCM has4,846,034 stereo sample frames, peak6571,
maximum adjacent step4490 and no clipped samples. These are basic completion
and output checks, not a timing/discontinuity diagnosis. Frame count differs
from parent's9089; no cross-ROM trajectory, renderer/DMA or speed equality is
claimed from completing the route. This long route still needs those observers.

Full unittest discovery:1436 tests passed in34.779 seconds. These supplement,
not replace, the executed game evidence. The broader suite includes historical
fixtures; it does not qualify every subsystem on3665.

## Remaining acceptance

Two fallback services occurred elsewhere in the pause/status route; their
lateness and critical-section ownership need direct investigation. Per-frame
once-only evidence is currently bounded to1430–1445, not the full route.
The new recover call has additional stack depth and CPU cost; real-game
register preservation, stack-wrap hazards and bank restoration need wider
execution checks. The cheap no-pending path still costs more than the old inline
policy. Full gameplay cadence, park combat, scrolling/renderer/DMA safety,
sprite/CHR publication, acoustic edges and physical capture remain unqualified.
Do not mark issues6,5,7 complete or deploy solely on the pause improvement.
