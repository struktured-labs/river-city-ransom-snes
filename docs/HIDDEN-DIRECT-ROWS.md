# Direct hidden-row uploads — faster loads, not yet deployable

The expanded [main-loop profile](../build/main-iteration-profile-281/report.json)
partitions each first-iteration call into ordinary NMIs and remaining elapsed
time, matching RTI stack restoration and rejecting nested/truncated interrupts.
Five new unit cases test that accounting. On candidate 265:

| Call | Inclusive clocks | Ordinary NMI clocks | Remaining clocks |
| --- | ---: | ---: | ---: |
| F293 → EFD4 (sprite list) | 361,106 | 272,546 | 88,560 |
| F299 → $8000 (game update) | 764,862 | 603,496 | 161,366 |
| F29F → FAE9 | 269,078 | 266,216 | 2,862 |

Remaining clocks can still include DMA/events. The game routines are unchanged;
the apparent FAE9 bottleneck is almost entirely interrupt work.

## Loading-only direct path

Default-off `experimental_hidden_direct_rows` requires attribute lookup and an
explicit bounded hidden-row budget. It is entered only in transition state 2
for an unqueued dirty row. It prepares 32 high tilemap bytes in unused scratch
`$7E55A0..55BF`, forces blank, and performs two 32-byte DMAs: original NES tile
bytes directly from the physical nametable shadow, then prepared high bytes.
A mirrored row is uploaded only if its flag is exactly 1. Queued states 2/3
keep their immutable old snapshots and the ordinary consumer.

The original shadow cannot change between the two transfers: the existing
producer bridge owns execution with NMI masked. Retirement occurs after DMA,
decrements the corresponding initial requirement without underflow, and leaves
all staging bytes untouched. The consumer still owns the final transition
barrier and unblank. State 0/1 use the original staged path. No game art or
logic changes. This is an explicit exception to the normal producer's
no-hardware-write policy, restricted to forced-blank loading.

The budget counts source rows as before; each may include one mirror, so the
maximum direct row transfer is `budget * 128` bytes (2,048 for budget 16).
This is **additional** to the consumer's separately bounded hidden transfers,
not a claim that a combined invocation retains the old 4,096-byte limit.
At budget 10 the producer can directly transfer at most 1,280 bytes.

Candidate `hidden-direct-on-282` SHA-256:
`c1b0409706a00aca3859fe76ea950c933f97612cffa3fb999bbf092cd46148e5`.
Default-off control 282 is byte-identical to parent 265.

## Executed evidence

[Full oracle](../build/hidden-direct-full-oracle-284/report.json): 1,856 cases
cover all 256 actually consumed attribute values, both mirroring modes,
pattern halves and all alias states. Each compares the full actual 8,192-byte
VRAM tilemap against an independent conversion, all staging bytes, original
shadow, row flags and initial requirements. Eight state-0/1 controls must leave
VRAM untouched and produce the original snapshots. Four executed mutants fail:
queued-alias overwrite, wrong high port, missing forced blank and wrong source
bank. The fixture starts in active display with forced blank disabled.

The initial partial run reached positive/policy checks but a generated include
path prevented mutation cartridges from assembling. The harness now preserves
the source directory in the include search path; the fresh full run above
includes actual executed negative controls, not compile failures.

[Neutral loading profile](../build/hidden-direct-neutral-load-285/report.json):
all 9,410 timeline rows and full PCM match the normal core. The first five
room-2 ten-row stages, now **including actual row DMAs**, cost
105,358–105,822 clocks versus roughly 124,000 for the parent's preparation
alone. These are measured stages, not a whole-game speed ratio.

| Build | First scenery after rendering-enable, rooms 1/2/3 | From room change | Stable late park packets |
| --- | --- | --- | ---: |
| NES | 7 / 7 / 7 | 20 / 31 / 30 | N/A |
| Parent 265 | 11 / 10 / 11 | 27 / 33 / 33 | 0 |
| Direct hidden rows 282 | 9 / 7 / 9 | 26 / 30 / 31 | 22 |
| Plus camera-edge fix 286 | 9 / 8 / 9 | 26 / 31 / 31 | 15 |

The [direct-row entry comparison](../build/hidden-direct-entry-audit-284/index.html)
retains all fixed-offset mismatches. One room reaches the original first-pixel
timing, but the all-room visibility/fade gates still fail. Its
[park audio timing gate](../build/hidden-direct-park-audit-284/index.html) also
fails. Changed combat evolution under fixed inputs is not a matched-state
performance comparison. No Rival deployment.

The follow-up trace uncovered a concrete missed-NMI race, separately documented
and tested in [Camera completion lost edge](CAMERA-NMI-LOST-EDGE.md).
