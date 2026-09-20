# Exact-state interrupt timing after restore

The known2239 combat stall is now traced from its actual saved state, without
reusing historical global timing counters or changing the replay's behavior.
This is diagnostic progress; speed, scrolling and audio acceptance remain open.

[Native audio, frame collage and complete timing evidence](http://127.0.0.1:8766/restored-clock-review-2899/).
All703 source bindings,21 served artifacts and four byte-identical native WAV
copies verify. The browser-rendered page was visually inspected. No MiSTer
upload, reset, controller input, SNAC change or OBS change occurred.

## A separately built, explicitly armed observer

`tools/build_replay_clock_core.py` copies the current Snes9x sources into a
fresh sibling and adds three host-only hooks. The historical sources and core
binaries are not edited. The new core is
`.deps/snes9x-replay-clock/libretro/rcr_replay_clock_libretro.so`, SHA
`625edec47a9ea7ac135aab7c777f16717fd52c995fa868806772c59f19592987`.
Its build receipt binds556 source inputs and the generated source/core/log.

After `retro_unserialize` and initial-state verification, an explicit API
starts a clock at zero. Each actual H-counter event adds the exact `H_Max`
which Snes9x subtracts from its scanline-local cycle counter. Instruction-entry
records, line events and host frame boundaries share that relative clock.
There are no emulated MMIO reads, guest writes, injected cycles or frame skips.

The host labels each `retro_run` with the corresponding replay frame. These
labels are not assumed to equal the old global instruction observer's labels.
The nine-frame windows2234..2242 each contain2358 actual line events; both1360
and1364-clock lines occur. The auditor reconstructs every record's clock from
the raw cycle/line-length fields and verifies every instruction-entry opcode
against the actual cartridge. It rejects shifted-clock and missing-line
mutants applied to each real trace.

## Two distinct neutrality checks

Checkpoint2839 frame2233 and old passing same-ROM control2844 remain the anchor.
Trials retain their whole-ROM-rebuilt, guarded replay references2871/2872/2895.
New plain runs2888/2889/2890/2896 execute90 frames with the new core, tracing off.
They match their respective old-core reference in every rendered frame, full
WRAM hash, recorded PC/P/DB, native PCM block/sample count and actual two-port
controller query/delivery log. Initial full WRAM and all CPU registers match
the saved checkpoint exactly.

Trace-on runs2891/2892/2893/2897 then match those new plain controls in all90
complete timeline rows, **all eight CPU register fields**, both controller
logs, full native PCM and initial/final full WRAM. Thus the changed core and the
enabled observer are qualified separately. This is not merely a screenshot
comparison or a claim based on the observer being nominally read-only.

## Matched-state result

All four runs show one unacknowledged VBlank flag rising at line240 while NMI
is disabled, and clearing at line0 with no hardware handler entry or software
event-count advance. The same original interrupt body spans that whole window.

|Variant|Original body entry|Body return after wrap|Body clocks|Clocks past line0|NMI re-enabled at line|
|---|---|---|---:|---:|---:|
|Parent2769|228:316|20:342|73678|27622|78|
|Fusion2868|220:978|10:470|70416|14110|68|
|Fusion+tile2869|220:994|2:956|59974|3684|61|
|Fusion+both-stride dirty cache2894|219:436|2:758|61698|3486|60|

Line:cycle values are actual beam positions. Body return is entry into
`nmi_rti_return`, not the completed native audio/preparation/interrupt epilogue.
The budget comparison uses the exact line0 boundary; the event-processing
observation can occur a few clocks after that boundary within an instruction.
The native return has more work before re-enabling, as the last column shows.

The new full-cache combination2894 is
`7d5899afb9a415c619b725b5e805a1b6fb07ab77991be6056b4a35df6b2e7832`.
It combines existing2807 ring code with the tested PPU stub fusion; its replay
guard rebuilds both components and checks the entire ROM and helper bytes.
It still does not advance either the native event count or game completion at
2239. Pictures match the parent through2240; completion still arrives on2240.
This additional experiment is not promoted and has no fresh full-route/menu/
DSP/physical qualification. Faster local code is not a passing speed result.

## Next implementation requirement

Preserve real pending events across long masked work, rather than inventing a
game update after noticing a counter gap. A bounded polling collector inside
the masked graphics path is one candidate: acknowledge the actual VBlank flag,
retain a distinct pending event, then service it exactly once after the current
game interrupt exits. That collector has **not** been implemented or qualified.

Required checks before using it:

- Already acknowledged events must not be collected again; events before,
  during and after each masked interval need independent execution cases.
- Preserve every caller's A/B/P/X/Y/D/DB/SP, mailbox and original PPU state.
- Do not advance the active audio-event identity while the previous event's
  sound update is still running; queued service must not double-publish sound.
- Native-mode bridges and original coroutine returns must not become reentrant.
- Late service must obey the existing VBlank DMA budget and retain queued
  graphics ownership; no visible-scanline bulk upload to force a timing pass.
- The saved-state2239 case must recover without moving a missed event earlier,
  followed by busy-NMI-inclusive combat, actual rendered camera cadence,
  menu, audio packet/native PCM and physical regression checks.

The initial workload includes slow copies, but the new trace rules out treating
another independently passing fresh encounter as recovery of this known state.

## Tests and reproduction

1215 unit tests pass (`/tmp/rcr-tests-2900.log`); seven new tests cover clock
reconstruction, missing/shifted records, cartridge opcode verification,
acknowledgment versus expiry, NMI-handler/count sensitivity, schema and exact
core insertion points. `git diff --check` passes.

```sh
python3 -m tools.replay_restored_instructions \
  --core-build .deps/snes9x-replay-clock/replay-clock-build.json \
  --candidate build/phase-balance-trial-2769 \
  --checkpoint-report build/ppu-register-checkpoints-2839/checkpoint-report.json \
  --reference build/ppu-register-control-2844 --out build/FRESH-NORMAL
python3 -m tools.replay_restored_instructions \
  --core-build .deps/snes9x-replay-clock/replay-clock-build.json \
  --candidate build/phase-balance-trial-2769 \
  --checkpoint-report build/ppu-register-checkpoints-2839/checkpoint-report.json \
  --reference build/ppu-register-control-2844 --control build/FRESH-NORMAL \
  --first 2234 --last 2242 --out build/FRESH-TRACE
```

The active goal remains incomplete. Rival's last deployed harmonic-wub2648
build and the offline phase-balance2769 baseline remain unchanged.
