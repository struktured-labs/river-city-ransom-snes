# Limited Run SNAC controller fix

Build 4299 was confirmed working by the user on Rivalmage through SNAC on
2026-09-28. Previously, the Limited Run controller's B button acted as Start
and other inputs were largely unresponsive. MiSTer mappings and SNES.CFG were
not changed. This is user-confirmed controller compatibility, not a claim that
physical rumble, original-console operation, or the whole game is qualified.

ROM SHA-256: `3b442dc89d88fe097fa758680373ef6e1679da4b67c5f856bd6bb19929c39246`.
Parent 4295: `e1b81f7df83b74ed7bd17d4d8f3602c489649e44f3d0ca1d72f7947bb1c0f596`.

## Implementation and attribution

Rumbleminze's [Castlevania SNES port](https://github.com/rumbleminze/castlevania-snes)
provided the architectural reference: automatic joypad polling for buttons,
and a separate, freshly latched 16-clock transaction before sending rumble.
See its `src/bank7.asm`, `src/bank-snes.asm`, and `src/rumble_controller.asm`.

`snes/autojoy_compat.asm` adapts that approach to RCR's input ABI. Interrupt
masking preserves automatic polling; hardware JOY register results are converted
to the existing cached NES serial bit order. The A-button jump shortcut remains.
The rumble transaction waits for polling to finish, prevents a new automatic
read during transmission, and restores polling afterward.

Build using `python3 -m tools.build_autojoy_compat`. This is an exact-parent,
guarded incremental builder, requiring the existing local 4295 artifact and
cc65 tools; it is not a standalone clean-checkout release build. It refuses to
overwrite the existing 4299 output. ROM binaries are not committed.

## Evidence and remaining gates

- Fresh emulator button checks pass: B does not start the game, Start opens
  settings, Right changes skill, and Start/story dismissal reaches gameplay.
  Local report: `build/autojoy-check-4299/report.json`.
- The 9,040-frame rumble-state replay passes pulse level/duration, pulse-off,
  and menu/pause silence checks. Event coverage fails because the scripted
  encounter did not observe BOSS. Full qualification is therefore not claimed.
  Local log: `build/autojoy-rumble-check-4299/log.txt`.
- Earlier manual-read timing trial 4296 passed ideal-pad checks but failed on
  the user's physical pad. Its builder is retained as a rejected experiment.
- Still needed before release: measure interrupt-wrapper timing overhead,
  complete event coverage, verify physical rumble and P2, and test the exact
  build on original SNES hardware. Existing broader release gates still apply.

Tracking: [issue #19](https://github.com/struktured-labs/river-city-ransom-snes/issues/19).
The build manifest records the pre-deployment state; this document and the issue
record the later user confirmation without modifying the bound build artifacts.
