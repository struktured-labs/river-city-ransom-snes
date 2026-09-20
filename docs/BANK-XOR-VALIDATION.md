# Equivalent bank mirror conversion retained

Latest default candidate: `build/bank-xor-01/native-cpu.sfc`, SHA256
`6ed6ccc84f0a212993bfe0f5a79d77532bbeb6813c22f13dd616c1cf021f50a1`.

The paired bank-switch adapter constructs program banks C1..C8. Converting
those to data banks 81..88 takes `EOR #$40` instead of `AND #$3F; ORA #$80`.
This removes one instruction per paired switch. Original input A, bank
variables, guards and final bank-tag comparison remain unchanged. This is
not a same-bank early exit and does not skip mapper state updates.

The executed adapter case 9 checks all eight program/data mappings and
registers. A new derived-ROM mutation uses XOR $41; it halts at the bank-tag
check in case 9, status 00, as required. The complete adapter suite passes,
including this negative control. All 129 Python tests pass.

Baseline remains 1956 frames; long route remains 7552. The route-progress
audit observes rooms 0,1,2,3 in order. Café CHR/menu checks pass, and the
stationary room-3 strip matches all 20480 pixels. Evidence:
`build/bank-xor-{route,shop,static-camera}-01`.

Moving-camera strips still fail, with the same 4152/3908/3881 differing
pixels as retained parent at matched cameras 5/110/215. Evidence:
`build/bank-xor-moving-camera-01`. No scrolling fix is claimed.

Audio receive comparison matches all 169395 bytes / 7365 packets. Raw-write,
length-eligibility, NMI coverage and ACK audit completes. Observer timeline
and full WAV compare byte-for-byte equal to the normal candidate capture.
Reviewable audio: `build/bank-xor-audio-audit-01/index.html`. This does not
prove perceptual fidelity or absence of pops.

This small CPU-work reduction is retained because the scoped regression
checks pass without additional guards or changed semantics. It does not
improve total frame counts or satisfy the original-speed requirement.
Experimental raster scheduling remains opt-in and unfinished. No Rival
deployment.
