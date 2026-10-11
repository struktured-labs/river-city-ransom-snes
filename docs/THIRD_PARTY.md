# Third-party provenance

No original game program, CHR data, extracted banks or generated game ROM is
tracked. The build requires a separate local original game.

| Dependency/reference | Revision | Use |
| --- | --- | --- |
| cc65/cc65 | e11fb5c39371046ebe25485f984f644c5a0d65d3 | ca65 and ld65, built locally |
| Myself086/Project-Nested | cc2c892be2e4f105a4780879022777b57f62052f (v1.8.1) | SPC700 2A03 sound engine source (`Assembly/Project/Spc700`), MIT; used by the `nested-audio` trials (4303 stock; 4304 with this project's SPC extensions, `Dmc.asm`/`Spc.Memory.asm` not assembled) |
| mandraga/upernes | d484e533bbd8335f9e0c6cc9272470f39c371419 | Memblers SPC binary (builds up to 4302) and host protocol reference |
| rumbleminze/nes-to-snes-template | 64958b6bb21d348d18e40f60e7bb110faae98d3f | Design/source inspiration, not vendored |
| infidelity | Development discussion and direct splash-screen guidance supplied by the project owner | Porting inspiration and window-mask reveal technique; no game-port source vendored |

## Contributor attribution

The project-facing credits are **struktured labs** for this port's development
and automated validation; **infidelity** and **Rumbleminze** for porting
inspiration/guidance; **Memblers (Joey Parsell)** for the original 2A03 sound
emulator running on the SNES SPC700; and **Myself086 (Laurent Courville)** for the
updated version of that engine in Project Nested, which the `nested-audio` trial
assembles. The engine is an actual build dependency, not merely an inspiration.
Credit both when describing our modified/experimental variants as well.

Infidelity's direct advice covered an 8bpp splash image revealed using the
horizontal window bounds, including the warning that a right bound left at
zero can hide the image. Acknowledging this advice does not imply his source
code was copied or that he endorses the resulting port.

## Dependency notices

### Project Nested SPC engine (nested-audio trial, build 4303)

`tools/pn_spc_asm.py` assembles `Assembly/Project/Spc700/Spc.asm`,
`Spc.Memory.asm`, `Dmc.asm` and `Data/*` from the pinned Project Nested
revision (fetched into `.deps/project-nested` by `tools/bootstrap.py`; every
file's SHA-256 and the assembled image hash are pinned in
`tools/dependencies.json`). Project Nested's own assembler is private, so this
repository carries an independent assembler for the subset those files use.
`tools/build_nested_audio.py` applies two documented engine patches (see
`docs/NESTED-AUDIO.md`).

Licence check at that revision: the repository's only licence file,
`License.md`, is the MIT licence, "Copyright 2020 Laurent Courville". No file
under `Assembly/Project/Spc700` has its own header, licence, copyright line or
exception, and no other notice in the repository (README, CHANGELOG,
Documentation) carves the engine out of the MIT grant. The repository does not
mention Memblers by name. The engine descends from Memblers' original, and
Memblers recommends this version. This project credits Memblers for the
original engine and Myself086 (Laurent Courville) for the Project Nested
updates, and carries the MIT notice below.

MIT notice, as required for copies or substantial portions:

```
Copyright 2020 Laurent Courville

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

### Legacy upernes engine (builds up to 4302)

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
