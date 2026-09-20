# Remove obsolete dispatcher NMI mailbox stores

General read/write dispatchers saved PPUCTRL bit 7 to `$1B26`, but no
runtime or generated stub read that field anymore. PPUCTRL also zeroed it.
The current stubs use live `$1C20` and the nesting/bank guards after each
transaction. Removing these three dead-write sites preserves the actual
NMI masking/restoration and special coroutine-tail logic. No new specialized
APU entry or engine change was needed.

Complete executed adapter tests, including missing-guard negative controls,
and all 103 unit tests pass. Candidate `build/dead-mailbox-01/native-cpu.sfc`
SHA: `43c6830e37399b2447640344f6c0ba329e25dcee28db1b74582574f1ec5cf0f0`.

The baseline finishes in 2,039 frames versus parent 2,043. The refreshed
original comparison at `build/dead-mailbox-quality-01/site/index.html`
still fails all four speed gates: boot/settings/story/street waits are
196/77/82/484 versus NES 170/53/54/459. The report's nonzero exit is the
expected performance failure, not a capture/build failure.

The 7,635-frame café/exit route still passes the fixed café menu and matched
room-3 strip comparisons at `build/dead-mailbox-{shop,camera}-audit-01`.
Its fresh bus/ACK audio audit at `build/dead-mailbox-audio-audit-01/index.html`
validates 7,392 complete acknowledged packets against ordered eligibility.
One two-frame gap remains in this run, plus scene-load gaps as large as 32
frames. Different combat states prevent claiming a causal same-state gap
reduction against older route captures. The fixed interior of the mall-load
gap remains exactly silent, preserving the demonstrated audio correction.

This is still not an original-speed or complete audio/scrolling release
pass. No Rivalmage deployment.
