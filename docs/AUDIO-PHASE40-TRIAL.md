# Earlier audio phase: local improvement, not a general fix

Previous goal turn made progress by measuring original-driver spacing directly.
The next instruction observation3723 is complete and neutral over9091 frames;
replay28.886seconds. Sources and full trace are bound by
`build/overflow-3526/audio-service-instructions-3723/service-instructions.json`.

At CPU frame2120, camera_deferred_nmi_exit's @publish at C7325C writes zero to
4200 at line79/cycle300. The next enable write is at line220 after the deferred
sound service. Within that masked interval, camera publication, retained original
NMI work and its return path run. Direct sound recovery starts line156; the
original driver starts line157. The line80 hardware service could not run while
4200 was clear. This identifies a scheduler/critical-section collision, not an
SPC-only delay. Longer driver execution also includes more original-driver and
APU-adapter work; it is not yet classified as unnecessary work.

Trial3724 changes only the eight replicated timer immediates and matching recovery
thresholds from80 to40, plus ROM checksum. Full accumulator preservation, depth
ownership, mapper guards and fallback semantics remain unchanged.
ROM SHA256: `bf197dbcb988bbf868f80df0da7dbf93787403a3bcbd22942eae66d7904e1db8`.

Fresh control3725 completes9091 frames. Observed3726 is exactly neutral against
that same-core control, including every primary timeline row and native PCM;
observed replay26.367seconds. Audit3727 retains8156 complete sound-driver calls.

At CPU frame2120, entry spacing improves21.493→16.639ms, and return spacing
23.617→18.762ms. But across the surrounding CPU frames1701–2399, the return-gap
range worsens from10.180–23.617ms to8.805–23.988ms. These are all calls in a fixed
CPU-frame region, not a claim of matched encounters or stable-gameplay coverage.
All intervals remain in audits3722/3727; no exceptions were removed.

Disposition: retain this experimental variant, do not promote it or launch broad
qualification based on the single improved gap. An earlier fixed timer phase
merely moves some critical-section collisions. Next assess service at safe
boundaries around retained work, and split request timing from original-driver
duration. Do not enable interrupts inside unprotected shared mapper/PPU state.

Loop accounting: immutable3695 control3706 reused with hashes revalidated;
only three CPU frames traced in detail. The current wrapper still replays the
whole route to check neutrality. These measurements are individual replay times,
not total turnaround or a controlled before/after test-loop speedup. A validated
short audio prefix remains useful work; broad renderer/DMA/context campaigns
were deliberately not launched for the insufficient phase40 trial.
