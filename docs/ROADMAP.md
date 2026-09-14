# Port milestones

The requested outcome is a playable native SNES conversion with unchanged NES
graphics and NES-style SPC sound. The audio diagnostic is an initial milestone,
not completion of that outcome.

1. **Implemented: foundation.** Strict original-ROM profile, lossless tiles,
   reproducible assembly, SNES boot and SPC pulse diagnostic, data tests.
2. **Needs original ROM: program map.** Record reset/NMI/IRQ, decode reachable
   code in all 16 PRG banks, identify banked data and indirect call tables.
   Inventory PPU/APU/controller/MMC3 reads and writes with traces. Rebuild the
   unmodified NES image byte-for-byte before changing instructions.
3. **Native boot and title.** Choose game memory map, implement bank switching,
   interrupt adapters, hardware access hooks, tile/palette/OAM upload and input.
   Match the original title with original assets and timing.
4. **Playable slice.** Match street scrolling, HUD split, two players, enemies,
   shops and transitions. Preserve original sprite data, animation and controls.
5. **Game audio.** Route original audio-driver writes through an event-aware APU
   bridge. Verify both pulses, triangle, noise, length/envelopes/sweep, silence
   and any DMC usage. Evaluate the Myself086/newer engine with matching protocol.
6. **Full-game validation and patch.** Play through with deterministic input,
   compare against NES captures, test real SNES, generate a source-ROM-validated
   patch and publish reproducible build instructions. Never substitute a renamed
   NES image or a diagnostic for the actual game.
