# Earlier stationary-camera interrupt scheduling

Follow-up: [physical menu and full-route audio diagnostics](HARDWARE-MENU-AUDIO-CURRENT.md).

Rival was restarted on September 17, 2026 at approximately 13:50:07 UTC with
branded candidate616, SHA256
`34835f853a6ce4bfebe4155c81014acd0a00bd8bf434969266e22b3bc22be72f`.
The process arguments name `RCR-SNES-34835f8.mgl`; the remote ROM hash matches.
OBS confirms the logo and subsequent 1P menu. No controller input was injected.
The old ROM/MGL remain available. SNES.CFG stayed byte-identical
(`066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`).

## Implementation and isolated tests

`experimental_static_camera_arm` is default-off and requires safe camera
publication and camera NMI re-enabling. Previously the retained-interrupt
scheduler first armed only after a camera difference. The new helper also
permits arming while stationary, once gameplay task, guard, pause, fade,
level and transition state permit it. It does not manufacture an interrupt
or change the original game graphics, sound engine or controller mapping.

Unbranded candidate608 is based on590. The option-disabled build is
byte-identical to590. `static-arm-oracle-609` executes29 real-beam hook cases,
four rejected guard/pause/fade/level mutants and a disabled control.
`static-arm-edge-control-610` retains the existing edge/acknowledgement tests.
Fresh scalar/paired CHR matrices614 and oracle615 cover256 cases and cache,
reader and pointer mutants. `static-arm-accounting-614` checks every sampled
frame boundary in four **unbranded** replays: all scheduled jobs served,
no final pending work, zero fallback. This is not instruction-level atomicity.

The selected stationary-camera CPU sample reduces NMI-to-sound-driver elapsed
time from48,884 to15,350 master clocks (`static-arm-cost-audit-613`). This is
one selected interval, not a claimed whole-game percentage speedup.

## Exact branded-ROM qualification

Candidate616 preserves the previous splash image, program, ident SPC payload
and pitch curve byte-for-byte. Its logo holds240 frames. Controller presets
remain disabled; this is not a controller-mode delivery or new bass design.

| Check | Result / evidence under build/ |
| --- | --- |
| Short movement | 21 pixels on both systems; every target no later; branded-movement-audit619 |
| Whole room loads | 20/28/29 frames versus NES20/31/30; branded-entry619 |
| Camera cadence east | SNES mean1.999372, max2.314160 nominal frames; NES1.999850/max2.353251 |
| Camera cadence west | SNES mean2.000400, max2.291069; NES1.999643/max2.379107 |
| Renderer splits | Zero across7,314 frames /1,170,240 street lines; branded-splits619 |
| Extra-frame stale holds | Zero across6,384 unchanged-camera frames; known582 failure caught; branded-held620 |
| Stable backgrounds | All774 selected positions exact; branded-background-audit619 |
| Present Status | First entry and reopening exact; branded-status-audit619 |
| Repeat shopping | Menu/repeat-purchase check passes; branded-shop-audit619 |
| SPC transport | All212,405 received bytes /9,235 packets match; branded-spc620 |
| Park audio cadence | No stable packet gaps over1.5 frames; branded-park-audit620 |
| Park interrupt window | Zero late intervals in7909..8729; branded-spans620 |

Directory prefixes in the table are `static-arm-`; cadence evidence is
`static-arm-branded-cadence-audit-619`. Complete observer timelines and PCM
match their normal-core controls. Different NES/SNES encounters prevent a
matched-combat/full-game speed claim. Old exact-fade, end-of-frame publication
and settling gates remain failing and visible; these results do not waive them.
The all-position background report is **not** an overall pass.

The branded key-on audit initially rejected the splash's additional startup
KON. It now requires the exact extra `(3, $033B)` event and known ident program
hash before the unchanged game startup sequence. Missing, duplicate,
wrong-value, wrong-site and late prefix tests reject malformed traces.
No arbitrary startup events or fixed frame grace period are discarded.
516 Python tests pass; `git diff --check` passes.

## Physical audio evidence from this restart

The existing OBS recording was left running; no scene, recording, replay,
mute or gain setting was changed. Read-only extraction uses
`/home/struktured/Videos/drmario_sessions/20260916_214537_struktured_v6c_part2.mkv`,
seconds43465..43495. The ident begins at43473.08. Report
`static-arm-rival-ident-621` passes all12 captured pitch checkpoints, silence
before/after, audible taper and original-game music resumption (RMS374.45).
This is real MiSTer/DeckLink audio, not the emulator WAV. The measured ident
has no overload/large splice step under the existing thresholds.

The nearby settings receipt identifies Blackmagic with mic/desktop muted;
it is not immutable historical routing evidence. Deployment identity uses
remote file hashes and process arguments, not cartridge-RAM readback.
This boot/ident check does **not** certify gameplay timbre, absence of
intermittent pops, all combat speed, or hardware playthrough.

Review with physical screenshots, sound and menu collages:
<http://127.0.0.1:8766/static-arm-review-621/>.

Rival launch mechanism was checked against upstream
[MiSTer command dispatch](https://github.com/MiSTer-devel/Main_MiSTer/blob/master/input.cpp):
the `load_core` command dispatches XML launchers through `xml_load`.
