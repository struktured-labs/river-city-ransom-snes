# Register-store PPUDATA specialization

The remaining-traffic profile identified FCF7 as a 64-byte constant
attribute fill (`STY $2007; DEX; BNE`) and E47A as a 32-byte palette
copy (`LDA $0110,X; STA $2007; INX; CPX #$20; BCC`). Both executed
192 destination stores in raw frames 250 through 320 of the profiled
settings window. These are different operations, not unbatched runs in
the decompressor.

Candidate `build/register-ppu-01/native-cpu.sfc` selected the existing
specialized PPUDATA dispatcher for absolute STX/STY as well as STA. The
generated stubs retain the original NMI masking interval, save flags/A
before TXA/TYA, and omit unused address-mailbox setup and generic dispatch.

All 113 Python tests and the full executed adapter suite pass. New executed
case 28 checks both register stores with distinct A/X/Y, NZCV preservation,
stale address-mailbox sentinels, changed output, address increment, write
counter and both physical/aliased staged-row dirtiness. Mutating TXA to TYA
or vice versa fails case 28. The fixture now contains four generated I/O
guards per bank; the existing guard-deletion tests still fail case 10.

Nevertheless the game baseline regressed from 1967 to 1971 frames:
168/58/61/484 transition frames versus parent 168/58/61/480. Settings
and story did not improve, and street now fails its existing speed gate.
Report: `build/register-ppu-quality-01/site/index.html`.

Production selection of the new register-store path was reverted. The
explicit stub-generation capability and its executed tests remain available
for future loop work; normal ROMs still choose the parent's dispatcher.
This experiment is not a speed improvement. Complete-loop batching remains
unimplemented and needs interrupt/state guards, not merely fewer per-byte
dispatch instructions. Audio popping is unresolved; no Rival deployment.
