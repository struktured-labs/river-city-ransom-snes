# Reset-aware SPC: second pulse and executed controls

The isolated SNES diagnostic supports `pulse2=True` with the retrigger
profile. It sends pulse registers $4004..4007 and enable/reset bit 1 rather
than the first voice's registers/bit 0. Every captured frame checks control
$BF, period $FD/$7E, channel enable 2 or 0, and periodic reset count.
The original NES fixture has a matching `--retrigger --pulse2` profile and
same-cycle suppressed-reset control. Default voice selection is unchanged.

`build/pulse2-phase-audit-01/index.html` compares four executed captures:

| Variant | Fixed-window phase repeatability, both outputs |
| --- | ---: |
| NES pulse-2 reference | 0.99302 |
| NES no-reset control | 0.17883 |
| Legacy paired SPC pulse 2 | 0.13839 |
| Reset-aware SPC pulse 2 | 0.98763 |

These use the same five constant-pitch events and thresholds as pulse 1,
without waveform alignment. The audit now rejects mixed pulse voices,
incorrect source-profile roles and failed source tone captures.

`build/pulse2-reset-controls-01/index.html` executes correct, missing-reset
and disabled-key-on variants. Correct schedule passes; both mutations fail.
The missing-reset mutation changes AND #3 to AND #0. The disabled-key-on
mutation replaces AND enable with AND #$FF. The oracle checks all 341 packet
flags, all new key-ons and the exact startup/legacy writes. Pulse-2 legacy
duty setup appears at SPC $05A7 with value 2; new key-ons at $302C use bit 1.
Normal-core and observer WAVs are byte-identical.

Pulse-1 controls likewise pass their expected outcomes in
`build/spc-reset-controls-02/index.html`. All 149 Python tests pass.
Sources: `build/pulse2-reset-{0,1}-01`,
`build/nes-pulse2-control-{0,1}-01`.

This verifies each voice individually, not simultaneous voices, dynamic
pitch/duty changes, exact NES waveform fidelity or gameplay popping.
The prototype's early KON plus existing duty-change KON can still cause a
duplicate on simultaneous changes; this must be addressed before integration.
Game builds and Rival do not use the reset-aware prototype.
