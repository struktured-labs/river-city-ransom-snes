# Skip redundant bulk-writer dirty work

`bulk_ppu_byte` now compares the decompressed byte with the mapped physical
PPU shadow before storing it and marking rows dirty. Identical bytes retain
existing dirty/staged flags; changed bytes take the old path. PPU and source
address increments, latch semantics, original register/flag result and the
write counter still run for every write. This is not skipped game execution
or a larger upload budget.

Executed adapter case 14 now repeats a byte into explicitly clean mirrored
rows, verifies they remain clean, and checks the write counter, address
increments and ABI. Existing changed-byte, page-carry, swapped-latch and
increment-32 cases remain. The removed-store mutant still fails, and a new
mutant that removes the identical-byte branch fails the clean-row assertion.
The complete adapter checks and 99 unit tests pass.

Candidate `build/unchanged-bulk-01/native-cpu.sfc` SHA:
`0cecaf8efba81476009f404f8a8c416de2583c2dd3bfd7830f41d4e143204398`.
Build with all six traces through `reference-shop-01`, as documented in
[shop coverage validation](SHOP-COVERAGE-VALIDATION.md).

## Measured results, not a full speed pass

Baseline capture: `build/unchanged-bulk-quality-01/snes`, 2,067 frames
versus parent 2,074. Recognized phase durations:

| Phase | Parent | Candidate | Original NES |
|---|---:|---:|---:|
| Boot to menu | 204 | 201 | 170 |
| Settings wait | 82 | 80 | 53 |
| Story wait | 86 | 85 | 54 |
| Street wait | 502 | 501 | 459 |

All four still miss original speed. The shop route completes in 6,451 frames
and retains the exact 17,380-pixel menu match against NES:
`build/unchanged-bulk-shop-audit-01/index.html`.

The 12,000-frame walk profiles (warmup 1,800) are retained at
`build/shop-speed-profile-01.json` and `build/unchanged-bulk-profile-01.json`.
NMI rate is 59.14 versus 59.65 per second; two-display-frame NMI gaps are
66 versus 22. Maximum gap remains 30. These are different encounter states,
not an aligned same-state timing experiment, so the gap reduction is
supporting observation rather than a causal gameplay-speed certificate.
Neither run reports the adapter's VBlank-overrun flag. Frame-boundary PCs
are sampling evidence, not cycle-accurate instruction attribution.

Audio fidelity, complete scrolling and original gameplay speed remain open.
No hardware deployment.
