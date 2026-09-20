# Direct SPC dispatch: measured audio-bridge saving

Review: <http://127.0.0.1:8766/receiver-dispatch-review-1928/>

Candidate `ec1c1ca53d6513bcb57d029e92948fde57f522d2e6ba33996deeb43bd7eb1768`
is an offline, default-off trial derived from current cartridge `0e9ba29becef`.
**No Rival restart or deployment in this turn.** This is an implemented
optimization with executed evidence, not a completed original-speed or
pop-free-audio fix.

## Change and measured result

The paired SPC receiver used an expanded conditional jump to its old wait
stub, which immediately jumped again to the empty-timer fast-path helper.
Retarget the first jump directly to that same helper. Only its two operand
bytes and two SNES checksum bytes change. CPU program, graphics, samples,
receive-store PCs, pending-timer body and sound command format are untouched.
Every preimage and the helper body are checked before patching.

This removes one three-clock SPC JMP per unmatched polling pass. It does not
skip Timer0 consumption, sweep work or packet checks. Elapsed packet savings
depend on sender timing and timer phase; a faster instruction path does not
mean every packet finishes sooner.

Fresh, complete instruction captures measure ten mall audio publications:

| Whole audio bridge, SNES master clocks | Parent | Trial |
| --- | ---: | ---: |
| Minimum | 23,976 | 21,850 |
| Mean | 25,041.6 | 23,972.2 |
| Maximum | 28,354 | 25,384 |

Mean saving is **1,069.4 master clocks / 4.27% of these audio calls**.
Individual slower calls remain in the report. This is not a 4.27% whole-game
speedup, an equal-work NES comparison, or proof that an audible pop is fixed.
Both profiling runs preserve their respective full normal timelines and PCM.

## Executed qualification

- Sixteen SPC cases: both frame-counter modes, sender delays 0/256/512/2048,
  101 packets then one second idle. Continuous half-frame deadlines pass;
  no unintended volume writes. A mutant discarding consumed timer ticks fails.
  Zero-delay packet costs are unchanged; delayed cases have lower means.
- Fresh normal/DSP/main/renderer/instruction captures complete the same
  9,406-frame route. Observer-on/off complete timelines and PCM agree within
  each variant; no result is inherited from the parent ROM.
- All **8,950 packets / 205,850 bytes** match actual receiver stores. No CPU
  bus leftovers, missing ready events, unexpected restarts or late restart
  configuration. All **1,638** restart checks pass; raw DAC matches delivered
  PCM exactly. This checks protocol/order, not perceptual fidelity.
- **3,823 stable gameplay loops** across rooms0–3 have two native-NMI ticks
  and consecutive two-frame starts. Both park directions have zero short
  irregular camera holds. Four eastbound/five westbound14-frame stops remain.
- All unchanged room-entry gates pass: first scenery7/7/7 frames after enable;
  room-change latency19/28/29; rendering-off latency20/29/29. Every fixed-offset
  background is exact against the original NES reference.
- [Full renderer audit](http://127.0.0.1:8766/receiver-dispatch-render-audit-1929/)
  reports no missing eligible coverage, scroll splits or stale held cameras.
- **992 unit tests pass**, including exact patch scope and damaged preimage
  rejection. Existing executable and cadence negative controls also pass.

## Differences and remaining gates

Parent/trial full equality deliberately remains **false**: 8,661 frame-state
differences and810 callback-boundary differences are retained in the report.
The optimization shifts sub-frame execution and sound timing; even with the
same route length, some rendered actor poses/positions differ. The review
shows actual same-numbered frames338,1542,5971,7522 without alignment.
This is not claimed as identical gameplay or universally improved latency.

Four audio excerpts are exact native sample slices from each version; no
normalization, resampling or perceptual verdict. The review and source hashes
are checked, including every served artifact. Room-entry evidence separately
retains all40 offsets per room.

Follow-up [combat/menu regression](DISPATCH-COMBAT-MENU-REGRESSION.md) passes
all four menu checks and sustained SNES combat; running/jumping retains the
same two room-transition stalls. The strict speed gate remains failed.
Next: qualified physical audio testing and remaining slowdown investigation
before promotion. The rare hardware slowdown, nonzero pops,
whole-game original-speed requirement and full-playthrough correctness remain
open. Rival stays on `0e9ba29becef` with the previous SNAC-enabled handoff.
