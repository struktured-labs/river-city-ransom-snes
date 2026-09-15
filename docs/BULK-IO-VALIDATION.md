# Decompression I/O overhead reduction

The complete decompression reader and writer already run under an interrupt
guard, but previously invoked the full per-register adapter inside that guard.
The reader now enters adapter direct page once and calls the shared buffered
PPU-read primitive twice. The writer directly performs its pointer lookup,
shadow store, dirty-row update, PPU increment, and write counter increment.
Both restore caller direct page and X before allowing NMI again. The reader
also preserves the carry/overflow state of the source-address calculation.
Graphics data and the original number of PPU reads/writes are unchanged.

## Tests and negative controls

The executed adapter suite passes all existing register/buffer/palette/CHR/
latch/increment cases. Case 15 now additionally checks overflow from source
address $7FFF + 1. The negative control substitutes PLA for PLP: it discards
the saved flags while balancing the stack, and must fail case 15. An earlier
NOP substitution was unsuitable because it unbalanced the return stack; that
experiment is not counted as flags validation.

Removing the first buffered read still fails case 15. Removing the direct
writer's shadow store fails case 14, independently of the existing wrong-
increment negative. Existing controller and jump tests also pass. All 77 unit
tests pass. The production build retains the tested triangle stereo fix.

## Measured result

Candidate: `build/bulk-io-core-01/native-cpu.sfc`, SHA
`af7883ec4103688b637b55e43a07837cbe006adf7ee1f979d1e9381d7809cc95`.
Baseline capture: `build/bulk-io-quality-01/snes`.
Dashboard: `build/bulk-io-quality-01/site/index.html`.

The baseline completes in 2,029 frames versus 2,035 for the preceding tested
triangle-corrected build. The read-only optimization first tested in
`build/bulk-read-core-02` saved just one frame; including the writer saves six
overall. Transition frames remain **208/63/70/488**, versus original NES
**170/53/54/459**. All four speed gates therefore remain failed; the settings
and initial-street pixel gates pass, as do input delivery and adapter-fault
checks. The independent report/media integrity verifier passes.

The 12,000-frame walk profile (`build/bulk-io-core-01/pacing.json`, measurement
after frame 1,800) has no VBlank overrun and a maximum observed NMI gap of ten
frames. The preceding profile had a maximum of 23. These runs can encounter
different room/combat states due to changed timing; that aggregate difference
is not a controlled proof that every loading gap fell by 13 frames, nor an
original-game-speed certificate. Scrolling transitions and audio fidelity
remain open.

This local candidate has not been deployed. At the user's request Rivalmage
was loaded with the earlier tested triangle-corrected ROM, SHA
`727f7083265524cb7e0b79d4cc4bd429caae935a6cf81eeeaff60a36b9456614`, via
`/media/fat/RCR-SNES-727f708.mgl`. The remote ROM checksum and running MiSTer
launcher were verified; SNAC CFG remained `00010000000000000000000000000000`.
The earlier `RCR-SNES-2d8dc7b.sfc` remains available for rollback. The ongoing
Rival session is left untouched by this optimization work.
