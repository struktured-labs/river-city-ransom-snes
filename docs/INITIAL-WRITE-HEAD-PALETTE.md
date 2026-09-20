# Initial palette publication through a safe write-command head

Candidate `build/pending-initial-head-344/native-cpu.sfc`, SHA-256
`070fb1dfae9dffe4f897366a6a940f6e5e8b9e73db7e7df0023e9f8e8520b7b6`.
**Experimental, not deployed.** First scenery improves from 9/7/9 to 8/7/8
frames after rendering-enable. NES is 7/7/7, so the loading gate still fails.
No original graphics, fade counters or sound assets are changed.

## Ordering proof and restricted implementation

The existing pending-palette path requires an empty original PPU command
queue. The new default-off `experimental_pending_palette_write_head` option
also permits a nonempty queue when its head is a WRITE command, its pointers
are within the 64-byte ring, and the fade generation at `$0692` is zero.
All existing pipeline, dirty-palette, interrupt and beam-position guards remain.
The builder requires both pending-palette preparation and the native ring
consumer. No queue entries are consumed by the preview.

Original C50B runs before the original palette copy. With `$003E` bit 1 set,
its budget is exactly one WRITE command. A WRITE head cannot change the fade
flags or original palette source; it exhausts the budget before a following
READ can run. READ commands can write arbitrary zero-page destinations,
including `$003E`, so READ heads must still be rejected. The classifier reads
the control byte at `(read + 2) & 63`. It uses eight-bit indexes and INX rather
than ADC so the caller's hidden accumulator byte and decimal mode cannot
change the ring lookup. The outer routine restores the native caller ABI.

The new runtime case 40 executes a wrapped WRITE followed by a READ aimed at
`$003E`. The real native consumer must stop between them, preserve fade flags,
advance the read pointer correctly and write the expected PPU shadow byte.
An executed mutation increasing its budget fails that case.

This is deliberately only the first fade generation for nonempty queues.
The broader prototype 341 previewed later generations too: it preserved the
palette bytes but made room 2's colors appear one frame early at offsets
10/14/18. Its failing report is retained in `pending-write-head-entry-343`.
Candidate 344 restores the established path for later nonempty generations;
empty-queue behavior is unchanged. No timing thresholds were relaxed.

## Executed checks

| Evidence directory under `build/` | Result and limits |
| --- | --- |
| `pending-initial-head-oracle-344` | 343 executed cases covering every ring start, WRITE/READ markers, invalid pointers, fade levels, actual CGRAM, source immutability and caller ABI. Four unsafe mutations rejected. |
| `write-head-consumer-oracle-343` | Actual consumer passes; four mutants rejected, including the new one-WRITE fade-budget violation. |
| `pending-initial-head-entry-346` | First scenery 8/7/8 versus NES 7/7/7. Whole room-change-to-visible 25/30/30 versus 20/31/30. Room 2 remains exact at all 40 fixed fade offsets. Overall **FAIL**. |
| `pending-initial-head-source1-346`, `pending-initial-head-source3-346` | Each observed initial preview matches all 25 distinct visible-color source bytes read by the subsequent original copy, within the same hardware NMI. Full 9,410-frame timeline and PCM match normal-core replay. |
| `pending-initial-head-park-audit-346` | Zero stable unpaused park packet intervals over 1.5 nominal frames; no native faults. The fixed route later leaves the park and pauses in the mall, so this is not endurance coverage. |
| `pending-initial-head-audio-346` | All 9,236 completed NMIs have verified packets, no unfinished tail and no unflushed CPU writes. Full PCM and longer transition-gap clips retained. **Not** a physical/acoustic pop-free or release-ready verdict. |
| `pending-initial-head-status-audit-349` | Both opening and reopening Present Status match NES with zero differing pixels and correct values from game RAM. |
| `pending-initial-head-movement-audit-349` | Short input-only movement regression passes against NES. Not combat or full-game speed certification. |
| `pending-initial-head-background-348` | Fresh exact-candidate sweep: 748 background positions, including 296 in the park, match in both y=32..79 and y=32..191. No late publications; full normal/observer timeline and PCM equality on both systems. The real broken-scrolling control is still detected. |

343 cartridge cases are separate from the **426 passing Python unit tests**.
The background audit revalidates the existing 80-case actual-renderer oracle;
it does not inherit the parent ROM's gameplay result. It retains the original
screenshots and 15 actor-overlap differences alongside independent background
planes. The same 64-position minimum applies to every room.
Integrated positive WRITE cases entering the publisher at lines 240/242
finish at 253/255; entries at 245/260 decline publication. READ heads leave
prepared colors unchanged, including at the early beam positions.

The source audits retain all parent differences without alignment: one
palette-source snapshot at frame 5665 and one fade-counter snapshot at 8135;
fade flags are identical. The source snapshot can catch a partially completed
generation at a frame boundary; it is not a claim of identical whole game RAM.
Observed preview/copy equality is checked at actual instructions, within the
same NMI, even when those instructions cross the core's frame boundary.
The four unused physical transparent shadow slots have separate synthetic
coverage; they are not mislabeled as 25-byte game-source proof.

An initial status capture omitted full-RAM telemetry and was rejected by the
checker before comparison. The fresh telemetry-enabled capture 348 and audit
349 above are the qualified result; the rejected invocation is not a pass.

## Refreshed loading profile and next target

`current-room1-profile-346` and `current-room3-profile-346` profile the prior
fully background-tested candidate 327, **not candidate 344**. Their complete
primary timelines and PCM match that candidate's normal replay. Actual ROM
JSR opcodes, matched return stacks and ordinary NMI boundaries are checked.

| First main-loop call to `$C7:8000` | Total master clocks | Inside ordinary NMIs | Residual |
| --- | ---: | ---: | ---: |
| Room 1 | 627,964 | 403,006 | 224,958 |
| Room 3 | 652,862 | 432,188 | 220,674 |

About 64–66% of the measured call is interrupt work. Residual time can still
contain DMA/events, so it is not exclusive CPU-instruction time. The first
`E343` service occurs at frames 2131/7074; that initializes fading, **not** the
first visible color. This updates the much older sprite-call starvation
profile: on the current parent, the long interrupted call is game update.

Next work is reducing measured hidden-load graphics preparation/interrupt
cost without starving audio or exposing incomplete rows. Full fade parity,
longer combat/endurance, exact-candidate café/pause integration and physical
gameplay sound remain open. Controller presets remain disabled. No Rival
restart was performed for this still-failing loading candidate.
