# Recurring audio-tick interrupt recovery prerequisite

Executed evidence: `build/overflow-3526/audio-tick-recovery-3660/report.json`.
This is an asset-free SNES cartridge, not a modified RCR build. The service
routine deliberately damages A/X/Y/flags; it does not generate sound.
The failed assembler attempt3659 is retained. A long branch fixes its range
error; no game cartridge or deployed configuration changed.

Seven fresh cartridge variants ran120 emulator frames apiece on the pinned
Snes9x core in0.362 seconds total (build, execution and checking). Each normal
case completes32 real NMI-generated epochs, tokensFFFD through001C. Service
claims the pending token before executing. Returning through a safe critical
section exit twice must not deliver it twice.

| Scenario | Actual service scanline, all32 tokens | Result |
| --- | --- | --- |
| Normal vertical IRQ80 |80|Pass|
| Interrupts masked40–60 |80|Pass|
| Interrupts masked40–110 |111, direct recovery|Pass|
| Interrupts masked40–250 |251, pending NMI fallback|Pass, explicitly late|
| Recovery removed |240 instead of110–113|Rejected despite balanced counts|
| Claim not cleared |111/113/240 duplicates, overflow|Rejected|
| Recovery corrupts X |111, correct scheduling but damaged context|Rejected|

The tests also check ordinary IRQ acknowledgement and absence of spurious IRQs,
pending-work retirement, and final main-thread A (including hidden B), X/Y,
decimal/carry/interrupt flags, DB, DP and stack sentinels. Register sentinels are
the final observation, not a complete trace of every interrupted instruction.
Source and output content hashes are recorded in the report. No ROM assets,
save states, or game captures need to be published to review this prerequisite.

## Integration requirements still outstanding

This establishes isolated E=1 interrupt ownership only. Production has mapper
critical sections, a coroutine NMI return, hardware-enable shadows and actual
sound-driver bank changes. It cannot simply replace their return handlers.
The game's existing early-audio token denotes an actually completed driver call;
deferred work must not be marked complete to suppress the existing NMI service.

Next apply the mechanism to an audio-only experimental game path, preserving
those owners. First repeat the paired pause test: current actual source-command
wait12.841ms versus NES2.415ms and PCM onset58 versus57 frames. Require actual
PCM improvement, unchanged ordered driver commands and no extra ticks before
expanding to gameplay cadence, scrolling/rendering and DMA qualification.
Neither this probe nor its counter balance proves pop-free sound or NES speed.
