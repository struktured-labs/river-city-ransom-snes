# Audio-scheduling trial: remaining menus and full-route DMA

The cartridge is unchanged from trial3065:
`964ef6c71257b89c1f9097ca6b4e2f9418b530057d5235e83f5e85c8ebd6711c`.

[Combined menu collages and qualification](http://127.0.0.1:8766/ordinary-early-audio-extended-3094/)
and [DMA envelope evidence](http://127.0.0.1:8766/ordinary-early-audio-dma-audit-3088/).
The earlier71.36% reduction in measured audio completion-interval spread is
preserved; this turn adds qualification, not a different sound engine or ROM.

## Additional executed checks

Fresh captures3081–3083 add17,453 frames across pause cursor return, two
consecutive café purchases and YES/NO traversal/confirmation. Audits3089–3091
pass every original fixed-region/CIRAM/shadow/VRAM check, while the retained
known-broken controls still fail. Together with prior status capture3072,
all four menu regressions pass across19,990 frames. `review_phase_balance.menus`
independently recomputes the oracles and revalidates2,110 capture/artifact bindings.

New sustained-attacks two-player campaign3092 has4,929 frames in both its
normal and observer runs, with identical input delivery, original RAM, video
and PCM. Strict and busy-inclusive cadence checks pass all1,753 two-frame
intervals. Running jumps already passed the same number. This expands combat
coverage without calling two policies a full-game original-NES speed proof.

## Actual full-route general DMA

A new sibling emulator build, `.deps/snes9x-dma-safety-3085`, adds a host-only
entry/exit observer to every `S9xDoDMA` call. The existing core and old source
files are unchanged. The build receipt binds557 inputs and the generated
core/source/log. Core SHA:
`76c66fd32fac40f93994ddd8a6192ecc00dd934f418043b5ca61b16f7fc179c0`.

The observer records actual PPU forced blank and screen height, beam positions,
source, B-bus target, mode, direction, count and remaining bytes. It does not
treat a game transition flag as evidence that rendering is physically blank.
The unobserved new-core capture3086 exactly reproduces prior route3068.
Observed3087 exactly reproduces3086: all9,248 frames and every PCM sample.

Audit3088 classifies all56,245 general DMA transfers:

| Classification | Transfers |
| --- | ---: |
| Display-memory envelope entirely within VBlank |54,386|
| Display-memory envelope with forced blank at both endpoints |1,855|
| Other target/direction |4|
| Aborted or unsafe/unproven display-memory envelope |0|

The latest visible-frame transfer ends at scanline257, cycle198 in this route.
This is **not** a replacement for the earlier synthetic heavy-palette result
that can finish at261. It is actual new-schedule route coverage, not an
exhaustive margin proof for every palette, entry subline, queue state or room.

The audit expands each DMA mode's possible B-bus targets and covers OAM, VRAM
and CGRAM. Active-scanout, cross-frame and unfinished-transfer trace mutations
are rejected. Four new unit tests cover true forced blank, a false transition
excuse, frame wrap, mode offsets, aborted transfer, malformed/empty traces and
changed instrumentation insertion points.

Scope: general DMA envelopes in the emulator, not HDMA or independent physical
SNES per-byte transfers. The source-built and observer-on/off neutrality checks
guard against changing emulated execution while measuring it. Full-game and
hardware qualification remain open.

## Hardware preflight

Bluemage was inspected **read-only** over SSH. It is reachable, currently
running `/media/fat/HOLES80_CVC.mgl` under an NES core, and has
`/media/fat/_Console/SNES_20240408.rbf` installed. No cartridge was uploaded,
loaded or reset; no controller events or configuration changes were issued.
Rivalmage was not accessed.

Blackmage OBS status was read without taking a screenshot or changing state.
Recording and replay were active. The current scene has one enabled Blackmagic
DeckLink capture source. Metadata does not establish which physical MiSTer
feeds it. The user has been asked whether Bluemage has a capture connection;
that remains unconfirmed. Existing Rival-specific launch/input helpers must
not be reused against Rivalmage or blindly retargeted to Bluemage.

## Verification / next work

Combined review3094 rechecks the prior qualification, all menus, DMA and
sustained combat, and binds3,521 sources/artifacts. No previous evidence was
overwritten. Full suite:1,257 tests pass; `git diff --check` passes.

The principal remaining audio requirement is physical self-verification with
a known Bluemage signal path and actual game input consumption. Do not infer
that emulator cadence improvement means pops are gone. Continue broader
original-NES workload and synthesis comparisons while resolving that path.
