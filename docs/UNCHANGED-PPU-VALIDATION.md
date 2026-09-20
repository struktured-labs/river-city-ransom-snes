# General PPUDATA unchanged-byte fast path

The general/specialized PPUDATA writer now uses the same mapped-shadow
comparison as the bulk writer. Identical writes do not create dirty work;
address increment and write accounting still occur. Changed writes retain
the previous dirty-row handling. Existing pending publication is untouched.

Executed case 24 checks all four row states (0/1/2/3), with different mirrored
alias states, against an identical write. It verifies state preservation,
write counter and PPU increment. Disabling the fast-path branch fails case
24. Case 10 explicitly seeds a different shadow byte before each repeated
guard test so it continues testing changed writes; its skipped-write and
missing-interrupt-guard controls remain effective. Complete adapter checks
and all 99 unit tests pass.

Candidate `build/unchanged-ppu-01/native-cpu.sfc` SHA:
`8cd064e18f8ac09487f62bf2b64eb69be523a60c042014a70d29c8a602e43a8c`.
Build uses all six traces through `reference-shop-01`.

Baseline `build/unchanged-ppu-quality-01/snes` completes 2,055 frames versus
2,067 for the bulk-only parent. Recognized boot/settings/story/street waits
are 198/79/81/497 versus parent 201/80/85/501. All still exceed original NES
170/53/54/459. The 6,439-frame shop route retains the exact 17,380-pixel café
menu match at `build/unchanged-ppu-shop-audit-01/index.html`.

## Audio remains a failed broader goal

`build/unchanged-ppu-audio-audit-01/index.html` binds the complete route PCM
to 6,197 acknowledged, byte-correct packets. There are still 23 two-frame
gaps and large scene-load gaps (30/31/32 frames across the run). Parent had
20 two-frame gaps; different encounter timing prevents treating either
histogram as an aligned same-state causal comparison. No audio improvement
is claimed. The fast path improves measured load waits but does not replace
the need to address long game-side stalls and synthesis/hardware popping.

No Rivalmage deployment.
