# Rejected four-row DMA extension

`build/row-quad-01` extended a ready pair to at most four contiguous rows,
keeping the 2048-byte total budget and existing beam preflight. Baseline
capture completed in 2008 frames versus paired-row 2011. Phase durations:

| Transition | Pair | Four rows |
| --- | ---: | ---: |
| Boot/menu | 186 | 185 |
| Settings | 67 | 66 |
| Story | 72 | 70 |
| Street | 486 | 487 |

Normal synthetic video, scrolling, late-budget, cache, CHR, clipping,
transition, and alias checks ran successfully. The suite then stopped at
the paired-row mutation locator because the new helper duplicated its
`cpx #127 / beq @done` signature. That is a harness identification failure,
not a passing four-row boundary test; no complete validation is claimed.

The small aggregate gain and slower street arrival did not justify retaining
the additional implementation. It was reverted to the paired-row source.
No hardware deployment. The next loading investigation should address the
rendering-off publication lifecycle rather than continue increasing batch
size without eliminating the observed frame delays.
