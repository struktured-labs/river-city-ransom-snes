# Rejected whole palette-copy batching

`build/palette-batch-01` replaced the checked E477 palette-copy loop with
a guarded batch. Only X=0, $3F00, increment-one, decimal-off copies with
game NMI disabled or nesting/bank guards set could batch. Other states
retained individual writes. The batch used the existing palette pointer
resolver, preserving transparent-entry aliases, and saved return V while
reproducing the final CPX flags.

The executed adapter suite passed, including temporary case 30 checking
all 32 physical palette bytes/unused alias sentinels, A/X/Y/NZCV, final
address/count, all unchanged row flags, and an unsupported-X/stride fallback.
This was not a full long-route or mutation-tested equivalence certification.

The actual game baseline was unchanged: 1963 frames with transition times
165/57/60/481. Settings and story still failed the existing speed gates.
Dashboard: `build/palette-batch-quality-01/site/index.html`.

The runtime, hook, fixture and guard-count adjustments were reverted.
Rebuilt `build/palette-batch-revert-01/native-cpu.sfc` exactly matches retained
`audio-data-first-02`, SHA256
`227dd74494a458fbc97baffb25fc4281601405994822c709f583afa42f188804`.
No hardware deployment or claimed performance improvement.
