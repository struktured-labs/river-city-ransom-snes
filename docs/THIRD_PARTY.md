# Third-party provenance

No original game program, CHR data, extracted banks or generated game ROM is
tracked. The build requires a separate local original game.

| Dependency/reference | Revision | Use |
| --- | --- | --- |
| cc65/cc65 | e11fb5c39371046ebe25485f984f644c5a0d65d3 | ca65 and ld65, built locally |
| mandraga/upernes | d484e533bbd8335f9e0c6cc9272470f39c371419 | Memblers SPC binary and host protocol reference |
| rumbleminze/nes-to-snes-template | 64958b6bb21d348d18e40f60e7bb110faae98d3f | Design/source inspiration, not vendored |
| infidelity | Development discussion and direct splash-screen guidance supplied by the project owner | Porting inspiration and window-mask reveal technique; no game-port source vendored |

## Contributor attribution

The project-facing credits are **struktured labs** for this port's development
and automated validation; **infidelity** and **Rumbleminze** for porting
inspiration/guidance; and **Memblers (Joey Parsell)** for the 2A03 sound emulator
running on the SNES SPC700. Memblers' engine is an actual build dependency, not
merely an inspiration. Credit its upstream authorship when describing our
modified/experimental variants as well.

Infidelity's direct advice covered an 8bpp splash image revealed using the
horizontal window bounds, including the warning that a right bound left at
zero can hide the image. Acknowledging this advice does not imply his source
code was copied or that he endorses the resulting port.

## Dependency notices

Bootstrap retains upstream repositories and their notices in `.deps/`.
The upernes README attributes the SPC700 APU emulator to Joey Parsell (Memblers),
2001–2003, with assistance from Kevin Horton and others. upernes includes GPLv3
text and describes its project as GPL. The separate engine's precise original
distribution terms are not established by a binary alone; do not infer a new
license for it. Rumbleminze's template has no top-level license in the inspected
revision. This repository references it without copying its source files.

The downloaded legacy engine SHA-256 is
`4e0951342dc2cf3ccc5caf1854e8cf7136aafa5d2ee137ea86c0b287b18a0f22`.
Generated diagnostic binaries embed this dependency and remain local; source
tracking does not include an upload of those binaries.
