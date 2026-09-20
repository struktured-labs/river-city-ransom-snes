# Retained interrupt fallback: recovered combat VBlank

Offline candidate `build/retained-producer-guard-2673/native-cpu.sfc`, SHA256
`d54feb304de5b6441fa19faa8d0aa6883397f83af0d1b74e1e57af0c3834ac28`.
Parent is the harmonic splash build2648 currently on Rival. No hardware input,
OBS change, restart or deployment was performed for this qualification.

[Same-state collage, native audio and full combat evidence](http://127.0.0.1:8766/retained-producer-review-2682/)
· [Full-route scrolling checks](http://127.0.0.1:8766/retained-guard-render-audit-2691/)

## Actual missed edge

Two-player input-only campaigns2669 select2P and mirror attacks/directions to
both physical controller ports. Start/Select are not mirrored. Both original
held-input bytes and both moving actor coordinates are checked. NES control
campaigns themselves contain three-frame intervals; that alone is not a
port-only slowdown verdict. All strict failures remain in review2672.

Instruction captures2670/2671 use the same core and match all4,934 timeline
frames and native PCM with observation enabled. Their bound trace identifies
the first stable running/jumping three-frame interval2290–2293:

| Executed instruction | Frame | Scanline |
| --- | ---: | ---: |
| Camera continuation requests retained NMI | 2291 | 197 |
| Original NMI return masks interrupts | 2291 | 238 |
| Pending-job fallback starts graphics preparation | 2291 | 239 |
| Second graphics preparation starts | 2292 | 13 |
| NMITIMEN re-enabled | 2292 | 34 |

Ordinary NMI entries occur at2289:240,2290:240,2292:240,2293:240; none at2291.
The earlier camera admission guard declines the late producer, but the retained
interrupt return's unconditional fallback bypasses it. Both graphics passes
run with NMI disabled across the entire VBlank. Enabling after the blank has
ended cannot recover that edge. Source receipt:
`build/two-player-instructions-2671/instruction-control.json`, trace sibling
`build/two-player-instructions-2671.csv`.

## Patch and executed ABI checks

Only two JSR operands per mirrored runtime bank are redirected to a256-byte
helper in previously FF-filled space at$7B00. The helper defers only when a
pending producer is already owned, the saved RTI continuation is exactly the
camera continuation, and the actual beam is at/after194. It does not consume
dirty flags or pending ownership. The next ordinary NMI exit retains fallback
responsibility. No game data, game timers, audio engine or graphics assets are
changed. The splash stays identical to2648.

The exact production helper bytes execute in oracle2677:60 cases and two
wrong-stack-page mutants. Cases cover both entry points, beam boundaries,
19 stack positions including page wrap, empty/pending jobs, ordinary/retained
continuations, and mirrored banks. X/Y/SP/DP/DB and all six saved interrupt
bytes are preserved. Downstream producers are dispatch spies here, not a
substitute for full-game timing or graphics tests. Failed fixture drafts2675
and2676 remain retained;2677 is the qualified oracle.

## Exact-state causal replay

Checkpoint2678 saves frame2288 without changing the original full capture.
Fresh-process same-ROM control2679 reproduces all90 replay frames exactly:
pictures, original RAM, registers, controller delivery and PCM boundaries.
Trial2680 permits only the freshly assembled guard patch, starts with identical
128KiB WRAM and all CPU registers, and receives the exact recorded two-port
input stream. It does not reuse historical instruction-trace counters.

At frame2292 the control's native NMI count stays1882 and original completion
counter stays151. The trial advances to1883 and152. Control completes at2293.
The first five pictures2289–2293 are identical; later timing/gameplay diverges.
Cross-ROM equality is deliberately false, while same-state comparison validity
is true. This is one recovered game frame, not original-speed certification or
proof that every later encounter has equal work.

## Broader regressions, including remaining failures

Independent two-player campaigns2674 have neutral full-timeline/PCM observer
pairs and exact port receipts:

| Stable start spacing | Parent two-frame / three-frame | Guard two-frame / three-frame |
| --- | ---: | ---: |
| Sustained attacks | 1716 / 18 | 1752 / 0 |
| Running/jumping | 1616 / 12 | 1635 / 3 |

Encounters differ; these are not matched-work speed ratios. Remaining stable
running gaps are2690–2693,2717–2720,2724–2727. Loads/pauses remain in strict
results, not silently dropped to make a release pass.

The8,874-frame four-room route completes. Renderer2688 equals its same-core
uninstrumented control2685 in every timeline row and PCM byte. Audit2691
checks7,266 eligible complete frames and6,304 held-camera observations, with
zero coverage/split/stale-camera failures. This does not certify every tile,
sprite, menu, or the older physical four-frame camera hold.

DSP2687/control2686 are likewise neutral. Audit2690 checks8,432 actual received
packets and1,548 restarts, with no late changed voice configuration; a damaged
late-write trace is rejected. Raw DAC equals4,730,880 native stereo samples at
32,040Hz, peak6,430, no clipping. These are transport/order checks, not a
pop-free, NES-waveform-fidelity or physical-audio verdict. Comparison uses the
older qualified2242 gameplay capture; the current trial is independently
bound to2673. Failed invocations2683 (wrong observer core) and2689 (incorrect
historical directory name) produced no qualified reports; fresh corrected
runs were used, without changing acceptance thresholds.

Full suite:1,178 tests pass (`/tmp/rcr-tests-2684.log`). Five added tests check
eight-bank patch scope/preimages, repeated/ambiguous/occupied patch rejection,
same-state counter recovery and unchanged-control rejection, missing inputs/
frames/RAM, and genuine second-player movement. Review2682's111 source bindings
and19 artifacts verify; its browser collage was inspected.

## Still required

Follow-up: [complete masked-path budget2696](MASKED-PATH-BUDGET.md) fixes both
admitted-producer states in exact-state replay but exposes remaining cases
where the original retained game interrupt alone crosses the entire blank.
It remains offline; an earlier graphics cutoff is not the complete solution.

Follow-up instruction control2692 and windows2693/2694 match all4,929 timeline
frames and PCM, including both port logs. They separate the remaining causes:

- 2690–2693 consumes three actual NMI advances, with ordinary entries at
  2690:240,2691:240,2692:240. There is no missing interrupt in this interval.
  It starts unusually late at2690:225. Original-work/coroutine timing still
  needs a matched NES comparison; it is not yet classified as acceptable.
- 2717–2720 loses the2718 interrupt. The camera producer is admitted at
  2718:191, starts its bridge at192, and returns at235. The original retained
  NMI then runs until2719:5, followed by another graphics pass. Interrupts
  are re-enabled at2719:45, after the entire blank is gone. Thus the old194
  cutoff leaves room for the producer alone, but not the retained game NMI
  and following producer. The new pending-only fallback guard cannot stop
  this path because the camera producer has already consumed the pending job.
- 2724–2727 also loses an interrupt after a camera commit at2725:189. The
  complete2716–2728 instruction window is retained for that second case.

These findings do not justify guessing a lower universal cutoff or discarding
the second producer. The next experiment must account for the complete masked
path and preserve graphics ownership, then demonstrate the same-state fix and
full-route publication behavior. Raw traces and source/neutrality receipts are
`build/retained-guard-instructions-2693{,.csv}` and
`build/retained-guard-instructions-2694{,.csv}`.

Requalify menu/status/shop behavior, one-player cadence and worst-case producer ownership before any
hardware promotion. Then capture Rival's actual scrolling/audio again. The
broader speed, scrolling and audio goal remains open. No current evidence
certifies original-speed parity, all physical holds, or pop-free sound.
