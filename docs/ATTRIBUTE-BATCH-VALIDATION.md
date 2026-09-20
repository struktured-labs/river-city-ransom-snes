# Guarded whole attribute-fill loop

Candidate `build/attribute-batch-01/native-cpu.sfc`, SHA256
`ca2e978b336ac20f67ec2996bf9a789c3a0a82d1deef649353ffc5d28c215517`.

The checked original FCF7 `STY $2007; DEX; BNE` loop now branches to
`bulk_attribute_bytes`. Only a 64-byte run beginning at an ordinary
nametable attribute boundary, with increment one, zero latch, decimal off
and game NMI disabled, uses the shared rectangular-fill engine. It saves
and restores all five borrowed decompressor variables. Unsupported states
retain individual PPUDATA dispatch and the original per-byte NMI guards.
A/Y/C/V are restored, X=0 and NZ match the final DEX, and the trampoline
resumes at FCFD's original LDX/RTS. Game graphics and SPC code are unchanged.

| Transition | Shared-repeat parent | Attribute batching | Original NES |
| --- | ---: | ---: | ---: |
| Boot/menu | 168 | 165 | 170 |
| Settings | 58 | 57 | 53 |
| Story | 61 | 60 | 54 |
| Street | 480 | 481 | 459 |

Baseline 1967 -> 1963. Settings/story still fail the existing speed gates;
street gets one frame slower despite the overall reduction. No tolerance
or input changes. Dashboard: `build/attribute-batch-quality-01/site/index.html`.
This is a small retained loading improvement, not original-speed parity.

Executed case 29 covers all 64 attribute bytes, all 128 dirty-row flags
(including retained staged bits and aliases), A/X/Y/NZCV, five saved game
variables, final PPU address and write count, and the NMI-enabled fallback
with a fixture nesting guard. It also checks increment-32 fallback and
zero-count 256-byte fallback. A mutation losing destination restoration
fails case 29. The repeated-run mutation locator was made more specific
because both wrappers now restore height/width; it still fails case 27.
Full adapter suite and all 113 Python tests pass.

The 7559-frame shop-exit route passes the café's exact 17380 fixed menu
pixels/CHR checks and room-3's 20480-pixel camera/scroll strip. The audio
audit verifies 7359 acknowledged packets, exactly one per completed NMI,
with no pending CPU writes or unfinished tail. Gap histogram:
1:7333, 2:6, 3:6, 4:3, 7:4, 8:1, 22:4, 32:1. Full WAV and every
multi-frame gap clip remain at
`build/attribute-batch-long-audio-audit-01/index.html`.

Independent stock-core capture `attribute-batch-long-normal-01/snes`
matches the observer's timeline and WAV byte-for-byte. These tests do not
certify every shop, encounter, movement speed, or perceptual audio quality.
Random popping and full-game speed remain unresolved. No Rival deployment.
