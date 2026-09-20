# Fade pipeline timing — measured, still late

The new observer reads the libretro core's advertised 128-KiB WRAM directly
after each frame. It does not read emulated MMIO, run CPU instructions, or
modify memory. It records the PPU palette shadow, converted-source cache and
prepared background/object colors. Capture receipts bind the observer source;
the verifier rejects malformed or unbound observations.

[Pipeline audit](../build/palette-pipeline-audit-276/index.html) compares
`palette-pipeline-272` with original `park-ppu-nes-210` and an unobserved replay
of the **same** candidate, `hidden-run-normal-269`. All 9,410 pre-existing
timeline rows and full PCM are identical with and without the observer.
The candidate ROM is `hidden-run-on-native-265/native-cpu.sfc`, SHA-256
`76bbf4784ecf5de1239a905256aeb9f3bee02f1d77c7dd27c005bf6c6b49ea72`.
The RGB555 lookup is checked against actual ROM bytes at its linked address.

Offsets below are frames from each room's first rendering-enable edge, not
manually aligned images. A completed original palette is identified by fade
level `$0692` plus dirty flag `$3E` bit 3, using all 32 game palette bytes.

| Room | NES first generation | SNES first generation | SNES shadow/cache/prepared BG | First scenery NES / SNES |
| --- | ---: | ---: | ---: | --- |
| 1 | 6 | 9 | 10 | 7 / 11 |
| 2 | 6 | 8 | 9 | 7 / 10 |
| 3 | 6 | 9 | 10 | 7 / 11 |

Thus there are two distinct delays: 2–3 extra frames before the first
completed game fade palette, then one extra generation-to-visible frame
compared with NES. These are frame-end observations, not exact intra-frame
CGRAM write times. Visibility is independently measured from actual pixels
in the fixed scenery band. Original code, not an accelerated replacement,
still computes the fade.

All four original/candidate generations have identical canonical NES indices
and resulting colors. Shadow and source-cache delivery are one frame after
each candidate generation. Room 3's last fade level changes NES indices but
not RGB555 colors (`$20` and `$30` both map to white). Its prepared-BG delivery
is explicitly **ambiguous**, not assigned an invented timestamp. The initial
audit assumption that all four levels must have distinct RGB values was wrong;
the final audit traces exact indices separately from RGB and tests this case.
Eight new unit cases cover alias writes, transparency, dirty flags, missing
or reordered levels, independent stage timing and this ambiguity.

## Updated main-thread trace

[Latest neutral instruction trace](../build/hidden-run-fade-profile-276/report.json)
repeats the original sprite-call accounting on candidate 265, rather than
assuming the older 93% interrupt result still describes optimized code.
Its complete timeline and PCM match `hidden-run-normal-269`.

| First room-2 F293 → EFD4 → F296 call | Master clocks |
| --- | ---: |
| Inclusive, frames 5661–5662 | 361,106 |
| One matching ordinary NMI | 272,546 |
| Outside that NMI | 88,560 |

The first sprite-list call is much shorter than the earlier 1,332,320-clock
case, but is still about 75% interrupt work. The first fade service is later,
at frame 5665, line 191. The remaining interval after the sprite-list return
must also be profiled; it is not justified to attribute the entire main-loop
delay to that sprite-list call.

A read-only follow-up over the same bound instruction trace finds the
first top-level F299 → $8000 → F29C call spans frames 5662–5664 and 764,862
elapsed clocks; F29F → FAE9 → F2A2 spans frames 5664–5665 and 269,078.
Both return-PC/stack matches are present. These are **inclusive** times,
not exclusive routine costs: the next profiling step must subtract matching
interrupts before choosing which translated operation to optimize.

No speed, scrolling or audio completion claim; no Rival deployment.
See the [FastROM consumer experiment](FAST-PUBLISHER-EXPERIMENT.md) for the
next measured optimization and its failing gameplay timing gate.
