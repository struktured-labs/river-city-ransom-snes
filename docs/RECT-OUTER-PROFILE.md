# Correct batching boundary: rectangular outer loop

Optional SNES instruction-count observer:
`tools/snes9x_cpu_profile.inc`, inserted immediately before opcode dispatch
in the pinned Snes9x `S9xMainLoop`. It counts host-side only, with no
emulated memory accesses or cycle changes. Built separately as
`/tmp/rcr-snes9x/libretro/rcr_cpu_profile_libretro.so`. Environment variables
`RCR_CPU_PROFILE`, `RCR_PROFILE_FIRST=250`, `RCR_PROFILE_LAST=320` select
CSV output and inclusive raw-core frame bounds. Run beyond the final frame
to flush it. Columns are raw frame, bank, PC, execution count; these are
not CPU-cycle measurements. Bank 00 code is grouped with its C0 mirror.

Both `cpu-load-parent-01/snes` and `cpu-load-rect-01/snes` match their
uninstrumented timelines and WAVs byte-for-byte. Counts expose the failed
inner-loop assumption: the rectangular helper was entered 782 times and
its byte loop ran 782 times, with zero fallback entries. The original
trace's C887 command bytes are all 81 in this replay: width one. The
actual repeated run spans the outer height loop, not the inner X loop.

The current experimental implementation patches the complete C88F outer
loop preimage. Width-one, zero-latch, increment-one, NMI-disabled,
nondecimal nametable runs can batch the height (zero means 256). Other
states/dimensions use the original nested helper loop. The fast path marks
the first changed byte in each eight-byte segment; with no NMI consumption,
this preserves both ordinary tile-row and attribute-group dirtiness.

ROM `build/rect-outer-01/native-cpu.sfc`, SHA256
`69df689ef00cdd803f1b54bf0892ff96f9e75e4b453f65e0e2071a1cdf938af8`.

| Transition | Audio-exit parent | Outer batching | NES |
| --- | ---: | ---: | ---: |
| Boot/menu | 177 | 172 | 170 |
| Settings | 62 | 59 | 53 |
| Story | 64 | 63 | 54 |
| Street | 479 | 486 | 459 |

Baseline 1982 -> 1980, but the street speed gate regresses. This is an
experimental worktree candidate, not a promotion over the audio-exit ROM.
Dashboard: `build/rect-outer-quality-01/site/index.html`. Settings, story
and street gates fail. No hardware deployment.

Executed adapter case 26 verifies a run crossing tile/attribute boundaries,
all expected dirty rows and aliases, a second unchanged run, destination
and PPU addresses, write count, A/X/Y and NZCV return state, zero-height
256-byte data, and a width-two nested-loop fallback. Skipping the store or
changing dirty-segment stride from eight to 32 fails case 26. The full
adapter suite and all 113 Python unit tests pass. More fallback states,
long-route graphics/audio, and the street regression still need validation.

## Follow-up route and street-wait attribution

The 7576-frame `rect-outer-long-01/snes` route passes the café's 17380-pixel
menu/CHR check and room-3 `mall_right_03` 20480-pixel camera/scroll strip.
The audio audit verifies one packet for each of 7348 completed NMIs, with
no unfinished tail. The normal replay `rect-outer-long-normal-01/snes`
matches both timeline and WAV byte-for-byte. These checks do not certify
perceptual popping or every scrolling encounter.

Delivery-gap histogram is retained at
`build/rect-outer-long-audio-audit-01/index.html`: 1:7322, 2:2, 3:4, 4:5,
5:2, 6:2, 9:4, 10:1, 22:4, 32:1. Both the remaining gaps and the changed
encounter timing must stay visible; shorter total capture is not an audio
fidelity score.

Street phase starts at absolute frame 511 and recognizes its HUD at 996,
versus parent 520 and 998. It therefore ends two frames earlier overall,
but its measured duration grows from 479 to 486. After the initial-row
guard clears, task C0 persists for 51 frames versus parent's 43. Every
adjacent display sample in each task-C0 portion increments NMI by one:
missing NMIs do not explain that residual difference.

All rendered frames are retained in `rect-outer-frames-01/snes`. Explicit
gallery `build/rect-outer-street-sequence-01/index.html` shows frame 946
still blank, 970 showing the street/introduction, 990 finishing text, and
994 showing the HUD. The benchmark completes its unchanged stable match
at 996. This locates the residual interval in introduction/HUD timing; it
does not establish the deeper cause or waive the speed gate.

`rect-outer-movement-audit-01/index.html` passes the short rightward test:
same 21-pixel displacement, with noninitial reference positions reached one
frame earlier by SNES. The unique-head checker retains actor-slot changes.
No full-game movement or combat-speed claim. No Rival deployment.
