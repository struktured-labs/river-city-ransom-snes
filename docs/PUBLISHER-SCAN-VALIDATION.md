# Grouped publisher queue scan retained

Latest default ROM `build/publisher-scan-01/native-cpu.sfc`, SHA256
`85de13c3c348baf739d249f39b607021891b810b6923ffcd4fe86f8248ba0ed9`.

Pre-DMA instruction profile `build/predma-cost-01.csv` covers bank-xor-01
raw frame 6831, NMI entry through the first STA $420B. It records 275
instructions, including 13 empty queue entries at nine instructions each
(117), before reaching a ready row. This is an actual publisher scan cost,
unlike the earlier mistaken producer/converter attribution. Observer full
timeline and WAV match the normal parent capture.

The publisher now checks eight row flags at once using four 16-bit loads/
ORs and mask $0202. Only a group with no ready bit can skip. X must be at
most 120 and at least eight of the original 32 queue visits must remain.
The skip advances X and consumes eight visits; wrap to zero is preserved.
Groups containing ready state 2 or 3 use the original scalar/DMA path.
No queue flag, conversion budget, publication byte budget or graphics asset
is removed. A long branch replaces the now-out-of-range backwards branch.

Validation:

- Complete executed graphics suite passes (scroll bands, late DMA guards,
  palette/sprite caches, CHR boundaries, masks, alias snapshots, row pairs,
  blank-load transitions). A new mask-to-zero mutant skips ready rows and
  fails executed case 5.
- All 129 Python tests pass.
- Baseline **1949 frames**, down from 1956. Long route **7545**, down from
  7552. Original-speed settings/story gates still fail.
- Room sequence, café CHR/menu and stationary room-3 strip pass. The latter
  matches all 20480 pixels. Moving-camera comparisons still fail.
- Actual SPC receive audit matches **169234 bytes / 7358 packets**, zero
  mismatches. Raw-write/length-eligibility, NMI coverage and ACK audit pass.
  Observer full timeline/WAV match normal candidate byte-for-byte. No claim
  of perceptual audio fidelity or eliminated popping.

Evidence directories share `build/publisher-scan-` prefix: baseline-01,
long-01, route-01, shop-01, static-camera-01, moving-camera-01, quality-01,
observed-01, audio-audit-01. Receiver report: publisher-scan-receiver-audit-01.json.

This is a measured speed improvement, not completion of speed/scroll/audio
requirements. Experimental raster scheduling remains separate and unfinished.
No Rival deployment.
