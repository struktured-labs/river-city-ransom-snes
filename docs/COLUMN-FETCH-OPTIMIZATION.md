# Column fetch: faster component, not a release candidate

`experimental_column_fetch` is default-off. It replaces original C2C3..C2E2
with a helper that unrolls the normal twenty-row column fetch and inlines the
ring-index wrapping. Other entry counts use a generic loop, including count
overflow. Original graphics, input mapping, sound engine and interrupt policy
are unchanged. No Rival restart.

## Why this loop

The neutral guard753 CPU trace756 showed C125 taking20,746 master clocks in
frame7776, versus1,506 in its neighbors. That scrolling-data work starts the
actor call later. Its intrinsic actor work remains161,880 clocks versus162,104
and162,026 nearby, but a70,066-clock ordinary interrupt extends elapsed time.
This is not evidence of unusually expensive AI in that particular stall.

## Executed qualification

- `build/column-fetch-oracle-766/report.json`:5,120 original/optimized pairs,
  each also checked against an independent RAM model. Covers all256 entry
  counts, all256 X values, all256 column values across the matrix, pointer
  page crossings, ring wrap, flags including decimal, and eight game banks.
  Every case records all zero page,256 possible first-write/ring destinations,
  A/B/X/Y/P/DP/DB/SP. This is not the full Cartesian product of those domains.
- Final full WRAM agrees except two expired original JSR return-address bytes
  and the terminal heartbeat. Six actual mutants are rejected. The earlier
  oracle759 lacked this final full-WRAM check;764 was superseded only by a
  clarified assembly comment.766 binds current sources.
- Per-row completed count is maintained, but one STA replaces two INCs: the
  intermediate odd count is not exposed. There are no injected interrupts in
  the isolated oracle, so it does not prove cycle-by-cycle interrupt-state
  equivalence. Do not hide this limitation behind full-route neutrality.
- `build/column-fetch-timing-767/report.json`:448 matched timed calls. Normal
  twenty-row fetch averages about9,951→6,472 clocks (roughly35% faster), saving
  at least3,456 clocks in the selected normal chunks. Short fallback chunks
  are unchanged; all timing cases and differences are retained. The observer
  preserves complete WRAM. This is not a35% game-speed claim.
- `build/column-fetch-patch-767/report.json`:4,727 changed ROM bytes,587-byte
  executed helper copied into eight unused regions, nine entry jumps and
  checksum only. All73 existing global runtime symbols remain fixed. Disabled
  rebuild763 is byte-identical to735. Current-source rebuild766 is
  byte-identical to758; the comment-only clarification changes no machine code.

## Full route rejects promotion

Unbranded758/current766 SHA256:
`2136002fc6eb8d6bd7696b47dd62782d4318d7aad4c185cf77873b33d15a9a6d`.
Branded760 SHA256:
`748bf895d54ac870305f5458c1b6057453eaa3756e5c4927605142ad1c229166`.
Branded column+deadline761 SHA256:
`e2577043ecdb40e270275747186e9b2afd6ec79dbcf51e547a908e2f5d871c42`.

Both branded candidates use the same existing supplied artwork and ident.
Normal/renderer762 agree over all9,054 and9,590 frames respectively.

| Candidate | East short irregular holds | West short irregular holds |
| --- | ---: | ---: |
| Before column, branded744 | 6 | 7 |
| Column760 | 28 | 21 |
| Before column, guarded753 | 12 | 25 |
| Column+guard761 | 27 | 2 |

`build/column-fetch-holds-764/` keeps every interval and long stop, including
the757-frame stop in the guarded return trip. Encounter states differ; these
are observed cadence distributions, not equal-work CPU-speed ratios. Better
return-trip counts cannot erase the worse outward cadence or long stop.

Renderer763 checks7,438/7,974 eligible frames and6,465/7,025 unchanged-camera
frames: no missing coverage, splits or extra stale holds. Both entry763 audits
pass all first-visible latency gates but fail exact fixed-offset fades. No
new background, menu, sound-provenance, acoustic or physical qualification.

## Regression harness improvement

CPU765 is neutral against the complete9,590-frame normal timeline and PCM.
Start/work767 show main beginning7832 line48 and camera completion at7833
line41. `build/column-fetch-pacing-case-768/` binds the actual instructions and
every street line to camera stores7830/7833/7834 and displays7831/7834/7835:
producer and display both have3/1 spacing.

The pacing-case auditor now optionally records variable producer intervals as
failure evidence; its default still requires2/2 production. Either irregular
production or irregular display fails. The old2/2→1/3 parent counterexample is
rechecked in768, so this extension does not excuse the earlier presentation bug.

594 unit tests pass. The component optimization remains available, but the
next work must address total main/interrupt/graphics scheduling and keep the
generation, cadence and audio gates intact. No game-speed or audio-fix claim.

The already-bound missed-VBlank750 trace further localizes the retained pass:
native_prepare→prepare_palette is38,638 clocks; palette→sprites is2,642;
sprites→prepare_tail is12,444. These are section elapsed times (initialization,
scans and events included), not exclusive per-row instruction costs. A full
late pass cannot be made safe merely by the roughly3,478 clocks saved in a
separate main-thread column fetch. Producer scheduling must respect the next
VBlank without dropping dirty rows, CHR, palette or OAM generations.
