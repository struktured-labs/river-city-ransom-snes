# Packet logger: coverage and initialization controls

September 18, 2026. No hardware, SNAC, OBS or recording changes.
[Control matrix and complete fade collages](http://127.0.0.1:8766/audio-packet-startup-review-1623/).

## The important correction

Earlier logger builds combined SRAM initialization with runtime recording.
Those experiments could not assign all gameplay differences to recording
overhead alone. New controls isolate the components:

- **SRAM mapping only:** same complete9,406-frame timeline and PCM as the
  deployed balanced-pitch parent's emulator capture. All NES entry gates pass.
- **Boot initialization only, no runtime logging:** reproduces the8/6/7
  visibility offsets instead of7/7/7 and fails the entry gates.
- **Initialization during a splash wait, no logging:** still fails. The
  existence of a wait does not establish that added work is fully absorbed.
- **Preloaded SRAM, no initialization instructions or logging:** preserves
  the entire9,406-frame parent timeline and PCM exactly; all entry gates pass.
- **Preloaded SRAM plus gated or continuous logging:** both still fail entry
  gates. Removing initialization does not make the runtime logger neutral.

These are executed same-policy controls, not an inference from final images.
Initialization is independently sufficient to disturb the tested result;
it is not the only source of disturbance. No exact attribution of every
later encounter difference is made.

## Selective recording and independent coverage

The gate tests original gameplay task, full fade level, native transition
state, rendering enable, fade flags, guard and pause. Rejected calls use the
unchanged original sender; accepted calls use the interleaved logger.
Even rejected calls execute gate instructions, so this is not a zero-cost
disabled path. The gate is not a production gameplay change.

`audit_gated_packet_log.py` joins exact CPU gate/dispatch observations to the
independent SPC receiver stream. A record's sequence selects its position in
the **recorded** subset, not the global packet stream; the native NMI and
all23 bytes must then agree. Missing/order/context/PC/count errors fail.

The boot-initialized and splash-initialized short runs each receive4,605
packets, record3,172 and explicitly omit1,433. Every retained record matches.
The preloaded variant receives4,598, records3,137 and deliberately omits1,461:
1,432 initial packets and29 during an interior interval. All3,137 retained
records match exactly. Full coverage ranges are published, including the
interior gap; no missing audio is inferred from an unrecorded interval.
Both normal and observed captures have identical full WAV, SRAM, WRAM,
frame metadata and final image within each variant. Actual wrong-receiver-byte
mutation fails. Unit checks include NMI wrap and record/global-index mismatch.

## Preloaded SRAM setup

`run_seeded_sram.py` installs an exact empty128 KiB RCRLOG01 image through the
libretro save-memory interface after game loading and before the first
`retro_run`. It verifies the entire readback and binds the seed, ROM, core,
capture command and wrapper source. It does not patch game WRAM, skip frames,
change clocks or load an emulator state. The no-logging control establishes
neutrality of this setup for the tested parent replay.

This is **not yet a verified MiSTer workflow**. Seed-dependent diagnostic ROMs
must not be launched without the required seed or treated as ordinary game
updates. The existing packet decoder rejects an uninitialized header.

The module runner emits a Python warning for the benchmark module already
being imported by shared helpers. Retain that warning; normal seeded-control
timeline and PCM equality are the executed evidence, not an assumption that
the wrapper cannot affect behavior.

## Artifacts and decision

Gate1589; normal/observed1590/1592; coverage1598; entry1593.
Boot-only1594/1595/1599; mapping-only1596/1597/1600.
Splash-gated1601..1604/1608/1609; splash-only1605..1607/1610.
Seed1611; seeded control1612/1617; seeded gate1613..1616/1620/1621;
seeded continuous1618/1619/1622. Combined review1623.

None of the active loggers passes the unchanged load/fade requirements, so
none is deployed. Reliable packet payloads and explicit coverage are now
established, but timing-neutral physical recording, the remaining audible
gaps and full original-speed fidelity remain open. Future work must separate
startup phase from per-transfer disturbance rather than treating every failed
logger replay as evidence of insufficient steady-gameplay CPU budget.
