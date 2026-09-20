# Original NMI versus port entry costs

Original NES observer `tools/fceumm_nmi_stage_trace.inc` captures
`build/nes-stage-01.csv`, frames 6800..6820. The full 7532-frame observer
timeline and WAV are byte-identical to `shop-exit-route-01/nes`.

At original frame 6812, NMI entry FF4F occurs at absolute CPU cycle
202835112; its first F1D3 restore sequence occurs at 202836073: **961 CPU
cycles**. Camera E2B1 occurs at 202839877, reported scanline 21. The first
sound IRQ service FA54 begins at line 31. F1D3 is shared by interrupt
epilogues: later occurrences at lines 61 and 193 are not additional NMI
returns. FCEUmm's scanline field remains 240 during VBlank, so do not read
the two 240 entries as a zero-duration interrupt; use the cycle difference.

Port observer `build/nmi-cost-01.csv` targets current default bank-xor-01.
Its complete 7552-frame timeline and WAV match normal `bank-xor-long-01`
byte-for-byte. It extends the existing stage observer with FF4F and updates
runtime restore PCs to 28C0/289D (not the older 28C2/289F).

Example across raw frames 6831..6832:

| Stage | Raw frame | Scanline | Master-cycle position within line |
| --- | ---: | ---: | ---: |
| SNES NMI entry 00:80FB | 6831 | 240 | 80 |
| Original game NMI entry C5:FF4F | 6831 | 254 | 88 |
| Translated original restore C5:28C0 | 6832 | 20 | 810 |
| Sound packet bridge entry | 6832 | 38 | 144 |
| Sound packet bridge return | 6832 | 51 | 318 |
| Graphics preparation return | 6832 | 134 | 506 |
| Camera E2B1 | 6832 | 181 | 484 |

Thus there is substantial delay **before** the added post-NMI sound and
preparation work: video publication holds original NMI entry until line 254,
and translated original work then extends past frame wrap to line 20.
Moving only post-NMI work cannot remove those costs. These samples describe
the same moving-mall route but are not an exact matched-instruction cycle
comparison across CPUs; original and port cycle units differ.

Next measurement should separate publisher DMA time from its CPU scanning
and compare translated NMI hardware transactions with the original NMI.
Do not assume the producer scan was the culprit: the preceding profile
already showed that broad-symbol attribution can hide conversion work.
No game code or Rival deployment changes in this observation.
