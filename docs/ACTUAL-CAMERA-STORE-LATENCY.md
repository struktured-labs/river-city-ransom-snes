# Actual camera-store to rendered-frame latency

The later [full-route original-NES comparison](FULL-ROUTE-CAMERA-LATENCY.md)
extends this park-only NES result and requalifies the SNES segment report.

September 18, 2026. Current ROM `071c89e` unchanged; no Rival input or restart.
Review and unaltered frame strips:
<http://127.0.0.1:8766/triangle-store-review-987/>.

## Result

| Sample | Changed commits | Same-frame display | Next-frame display | Missing |
| --- | ---: | ---: | ---: | ---: |
| Original NES, bounded park | 395 | 3 | 392 | 0 |
| Current SNES, park | 383 | 0 | 383 | 0 |
| Current SNES, four rooms | 930 | 0 | 930 | 0 |

The four-room join covers 7,211 stable rendered frames. Qualified changed
commits by room are 258/136/146/390. All 160 street scanlines must agree on the
actual rendered camera; incomplete or split observations fail. Every changed
store with complete surrounding renderer coverage is tested, not just favorable
examples. Unchanged stores and unqualified boundaries remain in the reports.

The original NES same-frame stores occur at frames 7365, 7535, and 7661,
scanlines 5, 9, and 15, targeting cameras 52, 184, and 285. The port matches the
original's usual next-frame delay but does not reproduce these three faster
cases in its differing encounter. This is not event-for-event equivalence,
full-game speed qualification, or input-to-display latency measurement.

## New observation and safeguards

`snes9x_main_store.inc` observes only four exact linked instruction addresses:
main-loop start, original input call, pre-`STA $F6`, and completion. It records
the actual accumulator, high camera bit, stack, original RAM context, native
NMI counter, and absolute host-observed clock without changing emulated state
or adding synchronization. The instruction opcode/operand and caller stack
are checked before reconstructing the actual committed camera value.

Capture 981 is exactly neutral to normal 891 across its complete 8,934-frame
timeline and WAV. Its 3,658 complete main iterations each contain a camera
store. Four additional nested transition stores at frames 2413, 5935, 6670,
and 7352 are explicitly retained separately, not assigned to a normal commit.
All normal commit values also agree with their frame-end camera RAM.

The original bounded main and renderer captures were requalified as 983/984
because older reports depended on a changed reporting implementation. Raw
captures and hashes were not edited. Report 985 joins the independently
qualified park observations. Report 986 extends the current SNES join across
all stable segments in rooms 0–3 using full renderer capture 895. Both
observers bind to the same independent normal capture 891.

Seven sparse-chain tests check actual accumulator/high-bit assembly,
instruction identity, caller stack, ordering, missing/duplicate events,
camera-free loops, nested transitions, and censored boundaries. Seven route
tests cover four-room requirements, missing/split cameras, invalid offsets,
missing timeline frames, pauses/transitions/disabled rendering, and retained
single-frame exclusions. Three publication tests require both original PNG
hashes and captured raw-video RGB hashes. Existing join tests catch missing
display and injected extra-frame latency. **721 unit tests pass.**

The review shows the first qualified changed store in each room as an
unaltered before/store/display strip. Every PNG is checked against the
capture's PNG hash and original decoded RGB video hash. No image synthesis,
cropping, alignment, or graphics changes are used.

## Remaining

The old strict background audit still fails its same-frame RAM/publication
rule at 885 observations. This work does not waive that gate or silently turn
those observations into a pass. It adds actual store-to-display evidence,
which the frame-end comparison alone did not provide.

Original-NES full-route store/display equivalence, hardware input latency,
broader endurance, and the three physical combat audio gaps remain open.
There is no new ROM to deploy from this instrumentation work.
