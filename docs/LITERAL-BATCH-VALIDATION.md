# Guarded literal-command batching

Retained `build/literal-batch-02/native-cpu.sfc`, SHA256
`5d559af582263c842a2316fa460c387de456d8f9cad80468288d6b5b49f4eec2`.

The original C872 source-read / destination-write / DEX loop now enters
`bulk_literal_bytes`. Its fast path requires count 1..63, NMI disabled,
increment one, zero PPU latch, decimal off, CHR source, ordinary nametable
destination, no source-index wrap, and no source/destination page crossing.
It resolves each source/destination pointer once, preserves transparent
source lookahead in the NES read buffer, marks changed destination segments,
and retains final original source/destination variables, data/mailbox,
A/X/Y and NZCV. All unsupported cases keep the original helper loop.
There is no change to graphics or the SPC binary.

| Transition | Data-first parent | Literal batch | NES |
| --- | ---: | ---: | ---: |
| Boot/menu | 165 | 165 | 170 |
| Settings | 57 | 56 | 53 |
| Story | 60 | 57 | 54 |
| Street | 481 | 478 | 459 |

Baseline 1963 -> 1956 frames. Settings/story still fail the unchanged gates.
Dashboard: `build/literal-batch-quality-02/site/index.html`.

Executed case 30 checks known CHR bytes crossing the destination tile/attribute
boundary, all 128 expected dirty flags/aliases, source lookahead/read mailbox,
game pointers/index/count and A/X/Y/NZCV. Fallback cases include destination
page crossing with physical CIRAM remap, source-index wrap, and NMI-enabled
execution under a fixture nesting guard. Omitting lookahead-buffer publication
fails case 30. The existing store/segment mutations now occur in both batched
engines and still fail the earlier case 26. Full adapter suite and all 117
Python tests pass. These are bounded tests, not every possible input state.

The final 7552-frame shop-exit route passes exact café menu/CHR and room-3
camera/scroll-strip comparisons. Receiver audit compares all 169395 bytes
across 7365 packets with zero mismatches. Ordered ACK/CPU auditing verifies
one packet per completed NMI with no unfinished tail or pending CPU writes.
Completion gaps: 1:7340, 2:5, 3:7, 4:3, 5:3, 6:1, 22:4, 32:1.
Full PCM and every gap clip: `build/literal-long-audio-audit-02/index.html`.

The independent stock-core long replay has byte-identical timeline and WAV
to the receiver-observed run. Full-game speed, broader scrolling/encounters,
perceptual popping and hardware validation remain open. No Rival deployment.
