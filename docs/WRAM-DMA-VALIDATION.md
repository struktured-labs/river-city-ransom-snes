# Reset WRAM clear using DMA

Candidate `build/wram-dma-02/native-cpu.sfc`, SHA-256:
`6b06329d03641ad26461c6b07d4d59741f84bad5ebbae57e42a4442766062ad9`.
Not deployed.

`snes/wram_clear.inc` is an inline reset-only operation shared by production
boot and the asset-free fixture. With native A8/X16, DB=0 and interrupts/HDMA
disabled, it streams a fixed ROM zero byte through WMDATA. Four 32KiB DMAs
clear the same 128KiB region as the old byte loop, including the stack. It
does not use a return address in that memory. Original game startup follows
only after the clear, and the build manifest binds the included source hash.

The initial two-64KiB version passed the memory oracle but failed the strict
capture invariant: a single transfer could span multiple video callbacks
within one `retro_run`. It is not the selected candidate. Each 32KiB transfer
is shorter than a display frame, allowing the core to return between
transfers without changing emulator speed or capture rules.

`tools/check_wram_clear.py` fills all WRAM with `$A5`, executes the shared
clear, and compares all 131072 bytes. The correct version leaves zero poison.
Two transfers leave exactly the upper 65536 bytes poisoned; one leaves the
upper 98304 poisoned. These controls explicitly fail the complete-zero
requirement while matching their expected incomplete-transfer footprints.
All three fixture results are bound to ROM/RAM/core/source hashes in
`build/wram-dma-test-02/report.json`.

The adapter suite and 94 unit tests pass. Retained-frame baseline
`build/wram-dma-quality-02/snes` completes in 2074 frames versus 2096 before
the clear change. Settings and initial street background pixel gates pass.
Boot-to-menu is now 204 frames versus the original NES's 170; settings,
story and street transitions remain 82/86/502 versus 53/54/459. All four
original-speed gates still fail. This is a startup improvement, not a fix
for ongoing gameplay stalls, shop/NPC graphics, or audio popping.

Web audit: `build/wram-dma-quality-02/site/index.html`.
