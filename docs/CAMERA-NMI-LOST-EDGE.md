# Camera completion can discard a fresh NMI

The longer gameplay gaps in the faster-loading candidate exposed a specific
interrupt race, not a reason to slow down loading again.

[Source-bound instruction audit](../build/lost-camera-edge-audit-289/report.json),
raw frame 8590 of `hidden-direct-stall-285`:

- The unretained camera hook begins at scanline 239, cycle 1062.
- Its `$4200` disable occurs before the new VBlank edge.
- The old re-enable wait begins at line 240, cycle 72.
- It polls 693 times, through line zero, before restoring NMI enable.
- No NMI entry occurs during that interval. The next is frame 8591.

All 9,410 timeline rows and full PCM match `hidden-direct-normal-284`. The
audit binds ROM/runtime bytes, labels, instruction trace and span trace, and
requires an actual STZ $4200 before the crossing. This is one proven lost
event, not an explanation of every audio artifact.

## Fix and hardware semantics

Default-off `experimental_camera_nmi_reenable` requires the deferred-game-NMI
scheduler. After the camera latches and iteration flag have been committed,
and only when no retained game interrupt exists, it immediately restores the
existing interrupt-enable policy. It neither waits out VBlank nor reads/clears
the newly pending event. The NMI handler already reads `$4210` at entry.

The flag is raised at VBlank even with NMI disabled; reading `$4210`
acknowledges it, and the flag clears at VBlank end. Acknowledging serviced
events avoids duplicates when re-enabling. See the primary library's
[PVSnesLib interrupt register documentation](https://alekmaul.github.io/pvsneslib/interrupt_8h.html).
The pinned SNES9x `ppu.cpp` implements these separate enable/acknowledgment
conditions. Waiting for the flag to disappear is wrong when it represents a
**fresh unserviced** frame, as this trace demonstrates.

## Executed edge harness

[Eleven paired timing cases](../build/camera-edge-oracle-288/report.json)
execute the extracted production camera hook against actual emulated NMI/MMIO,
not a mocked flag. The fixture uses RCR's line-240 overscan VBlank and varies
completion around line 239, plus fresh masked events at 241/250 and already
acknowledged events at 243/250. Every new case produces exactly one total
service before the next frame; registers, stack, camera latches and pending
state match. The old implementation drops the event in six cases.

Two additional controls fail the event-count oracle: clearing the fresh event
before re-enable loses it, and omitting the handler acknowledgment permits a
duplicate. An initial fixture wrote its diagnostic bytes outside bank-zero
WRAM; that fixture bug was corrected to explicit long WRAM stores before the
passing run. It was not counted as an implementation failure or a passing
negative control.

## Integration still incomplete

Combined candidate `camera-edge-on-286` SHA-256:
`3105eef248854b00ca0bcc2444ea782d6c640f495fb605605b3b5ce395edffc4`.
Default-off control is byte-identical to direct-row parent 282.

[Full park timing](../build/camera-edge-park-audit-287/index.html) improves
the worst stable packet interval from 728,346 clocks (2.0381 frames) to
620,206 (1.7355), but **15 intervals still exceed 1.5 frames**. These routes
have independently evolving combat; the controlled fixture, not just the
gap-count reduction, proves the lost-edge correction.

[Room-entry timing](../build/camera-edge-entry-audit-287/index.html) is
9/8/9 frames versus original 7/7/7. All-room original timing remains failed.
No physical deployment, full-game speed pass or acoustic-fidelity claim.
The remaining packet-phase variation and stage costs require further work.

[Normal-core equivalence and stage report](../build/camera-edge-neutral-spans-289/report.json)
matches all 9,410 timeline rows and full PCM. The bound timing window still
contains 11 late NMI-entry intervals; this is separate from the full-route
count of 15 late packet intervals. Neither measurement is suppressed by the fix.
