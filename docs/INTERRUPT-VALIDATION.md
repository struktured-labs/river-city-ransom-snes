# Incremental interrupt checkpoint

Candidate SHA-256: `2098a778f32cadfa886a6dafc59e6f9303342ba9d55d70ed6135bb12402ab4ca`.
Original graphic indices and artwork are unchanged. See [implementation](NATIVE.md)
and the [private collages](audit/README.md).

The same scripted walk, emulator and display frames 1801–3600 give:

| Measurement | Previous publisher | Incremental publisher |
| --- | ---: | ---: |
| Visible picture changes/second | 1.77 | 11.45 |
| Original game-tick changes/second | 13.22 | 11.95 |
| Native NMI counter increments/second | 31.32 | 32.32 |
| Longest NMI gap, display frames | 60 | 74 |
| Black display frames | 71 | 26 |

This is about 6.5× more visible updates, **not** 6.5× faster gameplay or a
full-speed port. Input schedules are identical but game phases diverge, so this
is a workload comparison, not synchronized gameplay benchmarking. Scene-load
stalls and choppy sound remain. The baseline lacked the new VBlank guard.

The new candidate passes 12,000 emulated frames with advancing native NMI
counters and no detected publisher overrun, unknown-I/O fault or SPC timeout.
That establishes liveness, not complete gameplay or audio correctness.

`tools/check_video.py` builds an asset-free cartridge using the production
producer and consumer. It tests two generations, nonadjacent dirty rows, a moved
sprite and a background pattern-table switch against an exact full-frame pixel
oracle. CI also runs the existing native adapter positive/negative controls.
The synthetic cartridge uses native-mode interrupts; the actual game soak
exercises RCR's emulation-mode coroutine adapters. Neither proves real hardware
compatibility.

Reproduce:

```sh
make verify
python3 tools/check_video.py --core /path/to/snes9x_libretro.so
python3 tools/profile_native.py --core /path/to/snes9x_libretro.so \
  --rom build/incremental-final-04/native-cpu.sfc --out build/pacing.json
```

Next timing work: isolate the original game's coroutine waits, bank/PPU hooks
and SPC handshakes. Do not use the higher visible-update rate as evidence that
the original game clock or sound sequencing is now correct.

## Interrupt-mask diagnosis, 2026-09-15

Local mono-routing candidate `d058e05d038513bbb703c20d82b75525a878e12821d0187fb610328dc06c7f36`
was run for 3,600 display frames with the `walk` input profile. The instrumented
core SHA was `e62e8d9e636db679be95f19262d582cca41abc83a46ac27ddac92e53be004bf2`.
Its PCM hash matches the prior stage-instrumented execution:
`cb76fb9a236c03c7c0071ea5fc433c815aae6a3d0c4027cda067c0cd654a41c9`.
The transition trace starts at emulator frame 1800; it is local ignored evidence
at `build/mono-audio-01/enables.csv`, SHA
`388383a357b16e610a939240760722a62973ef1f675b4ab4826b9e55f474bc5f`.

Across completed interrupt-masked intervals, 757 line-240 VBlank edges were
masked. Of these, 568 fall in intervals opened by `bank_switch_enter` (trace PC
Cx:2354, immediately after its STZ $4200); 124 fall in intervals opened by the
NMI handler itself, and 65 in other adapter paths. These are mask-edge counts,
not an independent original-game-speed or audio-fidelity oracle.

Example: the bank switch at frame 2134, line 238, cycle 1082 disables NMI.
It re-enables at line 0, after the VBlank edge has passed. The exit adapter
explicitly waits outside VBlank. Similar bank-switch intervals mask the next
two edges; the next recorded NMI entry is frame 2137, line 240. Stage tracing
also shows a roughly 62-line clean graphics preparation cost, with longer
preparation when dirty rows are converted, sometimes repeated by PPUMASK.

The paired-bank guard must remain: removing it previously allowed sound NMIs
to corrupt an unfinished R6/R7 switch. The next implementation experiment is
safe late-NMI delivery **after** the pair is complete. This also requires a
late-entry graphics budget check: the final OAM/CGRAM batch is currently
unconditional, so merely deleting the VBlank wait is unsafe. Coroutine stack
shape, no duplicate delivery, full settings pixels, long walking progression,
and audio cadence still need regression coverage before hardware deployment.

The tracked SNES9x debug patch now exposes `RCR_ENABLE_TRACE`. CSV columns are
frame, beam line, cycle, PC after the write, NMITIMEN value, task, NMI depth,
bank guard, and shadow PPUCTRL. It records changed writes after frame 1800.
`tools/analyze_nmi_mask.py` assumes NTSC non-interlaced line-240 NMI and handles
the core's frame counter advancing at line 1 rather than line 0. It ignores
an incomplete final interval and reports that limitation. Five unit tests
cover normal entry, an edge crossing, line-zero wrap, multi-frame masking,
and out-of-order evidence rejection.

```sh
RCR_ENABLE_TRACE=build/enables.csv python3 tools/smoke_libretro.py \
  --core /path/to/instrumented/snes9x_libretro.so \
  --rom build/mono-audio-01/native-cpu.sfc --kind native --profile walk --frames 3600
python3 tools/analyze_nmi_mask.py build/enables.csv --out build/masked-edges.json
python3 -m unittest discover -s tests
```

All 46 unit tests pass at this checkpoint. No new runtime change or Rivalmage
deployment is claimed by this diagnostic work.

### Late bank-exit delivery experiment

Candidate `build/late-bank-03/native-cpu.sfc`, SHA
`754bbf0d37bc3f5c5a965ce5f42a64dc7326ff06ab2faf51121787754e275a33`,
removes only the bank-exit wait-outside-VBlank loop. The atomic pair/depth
guards remain. NMI entry already acknowledges $4210; bank exit can therefore
deliver a still-pending edge after completing the pair. The publisher now
rejects late entry, reserves another scanline for row DMA, and checks the
remaining budget again before its final OAM/CGRAM batch. Early experiments
without that final check failed the overrun oracle and are not candidates.

The 12,000-frame walk has no detected VBlank overrun, adapter fault, or SPC
timeout. Over frames 1801–12000 it measures 53.99 NMIs/second, 16.18 picture
changes/second, and 13.81 sampled game-counter changes/second. The preceding
block-OAM baseline measured 37.27, 13.51, and 17.30 respectively. Thus this
recovers interrupt delivery but **does not demonstrate faster gameplay**;
the game-counter metric actually decreases. Different scene occupancy also
prevents treating these whole-run metrics as matched game simulation speed.

The phase audit in `build/late-bank-quality-03/site/index.html` has verified
bundle integrity, passes its settings pixel and basic audio activity gates,
but still fails all four transition timing gates. Native capture takes 2672
frames versus the NES reference's 1936 (the previous mono candidate took
2425). More frequent interrupt work leaves less main-thread time; reducing
producer/adapter overhead is the next target. Basic audio activity does not
establish musical timing, absence of sputtering, or sound-effect fidelity.

The asset-free graphics harness includes a deliberately delayed first NMI at
line 260: staged rows must remain queued and subsequent normal interrupts must
produce the exact expected image. Removing both late-budget guards must fail
the executed assertion. The test checks both frame-counter bytes so it does
not accidentally repeat at counter 256. This candidate is local experimental
work, not a deployment or a full-speed release.

### Cached preparation follow-up

`build/cached-producer-01/native-cpu.sfc`, SHA
`9b891eed491664e393510eb7b6293947cdad3caad67973f83e252470856b19a1`,
compares actual palette and OAM shadow bytes before reconverting them. Palette
snapshot storage is $7E5580–559F; OAM snapshot storage is $7E5600–56FF. The
sprite pattern-table bit is cached separately at $1C86. The existing first-
publication flag forces initialization even when zero-filled source and cache
match. Unused SNES sprites/high OAM are initialized once. All comparisons and
publication snapshots remain inside the NMI-masked producer bridge.

The same 12,000-frame workload measures 55.16 NMIs/second, 19.09 picture
changes/second, and 15.93 game-counter changes/second, with no detected VBlank
overrun or adapter/SPC fault. This improves on late-bank-03, but still does not
establish original-speed gameplay. Street-scroll samples reach 440 rather than
511 in this run; neither range proves traversal or identifies a scroll failure
without a phase-matched positional oracle.

The audit at `build/cached-quality-01/site/index.html` verifies bundle integrity
and passes its settings pixels/basic audio activity gates, but all four timing
gates still fail. Its SNES capture is 2642 frames versus NES 1936. The full
audio-fidelity and physical-hardware release requirements remain unverified.

The graphics test now changes palette bytes and toggles the sprite pattern bit
while OAM is unchanged, checking staging contents before restoring the final
pixel oracle. Mutants that ignore either change must fail executed assertion
7. Normal, scrolling, late-entry, lost-row, disabled-HDMA, and cache-invalidation
checks pass; 46 unit tests pass. No Rivalmage deployment was performed.

### Ordinary adapter return overhead

`build/lean-return-01/native-cpu.sfc`, SHA
`8e58e706bab2cd0d29cdc264df83d711e862e78cf1fbaa918c845b00cf93e01a`,
splits the ordinary adapter return from the bank-changing return. Previously
every PPU/APU/controller access rewrote its JSL return bank and DB. Only the
R7 pair-completion path changes the active PRG bank; ordinary calls now restore
the existing saved registers and RTL to the bank already on the stack. The
atomic bank-switch guard and bank-changing stack rewrite are unchanged.

The same 12,000-frame workload measures 56.98 NMIs/second and 22.93 sampled
game-counter changes/second, versus 55.16 and 15.93 before this change. Picture
changes measure 18.80/second. No adapter/SPC fault or publisher overrun was
detected. The camera/HDMA scroll samples span 0–511; that is not a verified
scene-exit or right-edge traversal test. Workload phase differences still
prevent interpreting these counters as a matched original-speed verdict.

`build/lean-return-quality-01/site/index.html` has verified bundle integrity.
Settings pixels and basic audio-activity gates pass; all four transition timing
gates still fail. SNES capture takes 2588 frames versus the NES reference's
1936. No claim of full sound fidelity, original speed, or hardware readiness.

The asset-free adapter fixture now replicates its code/runtime in C1 and C2,
executes an actual R6/R7 pair change, and checks PB=C2, DB=82 and preserved
A/X/Y. An ordinary PPU call from C2 into the C1 helper must return to C2 with
DB unchanged. A mutant that bypasses the bank retarget fails assertion 8.
The existing truncated-OAM mutant now changes both runtime copies. Adapter
positive/negative controls and all 46 unit tests pass. Rivalmage is unchanged.

### Direct paired-bank translation

`build/direct-bank-01/native-cpu.sfc`, SHA
`a0c9e320821e74cb0f4dd117e5b639e7ea3e00126262201a176f950494a86df9`,
replaces FED1's four general mapper accesses with their direct paired-bank
effect. The recognized ROM routine computes R6=2*A and R7=2*A+1, leaves FB=7,
FC=R6, FD=R7, preserves A/X/Y, and compares A with the destination bank's BFFF
tag. The new code does those updates while NMI remains masked, then uses an
indirect long jump through $1C88–1C8A to the replicated checked exit. The exit
still validates the bank tag and only re-enables NMI when both depth guards
allow it. The old diagnostic count of generic R6 dispatches is no longer
incremented by this direct path. No original artwork or gameplay wait threshold
is changed; input ROM PRG/CHR checksums remain enforced.

The 12,000-frame walk measures 56.99 NMIs/second, 29.78 picture changes/second,
and 25.90 sampled game-counter changes/second, compared with 56.98/18.80/22.93
for lean-return-01. No adapter/SPC fault or graphics overrun is detected.
The phase audit at `build/direct-bank-quality-01/site/index.html` verifies
bundle integrity and basic audio/settings gates, but all four transition
timing gates still fail: capture length 2533 versus NES 1936. These remain
experimental results, not proof of original-speed gameplay or clean sound.

The matched direction-reversal capture is visibly closer to the original:
after the same 1440 Left frames, the old native candidate's camera bytes were
3501 and the new candidate's are 2500; NES is at 0000. The new native image is
near the school entrance, rather than farther down the initial street. Different
encounters preclude an exact speed ratio. The retained paired images/audio are
at `build/direct-recovery-01/site/index.html`; full original-speed and audio
fidelity requirements remain open.

The asset-free fixture now replicates all eight runtime/program banks and
checks direct switches through each pair, final equality/carry, A/X/Y, PB/DB,
FB/FC/FD/R6/R7, and cleared critical depth. An incorrect R7 calculation fails
executed assertion 9. Existing ordinary-bank, controller, jump, CHR and OAM
positive/negative tests still pass, as do 49 unit tests. Rivalmage is unchanged.

### Pending interrupts after ordinary I/O

`build/late-io-01/native-cpu.sfc`, SHA
`09194e5524ee25d7c7108308b19c814043473915a6678fff9b2d8c2d281e6fcc`,
removes the wait-outside-VBlank loop from completed ordinary mailbox stubs.
The enable path uses its existing masked PPUCTRL value without reloading it.
Both the active-NMI and paired-bank guards still suppress enable. PPUCTRL's
special coroutine tail and the original NMI return path are unchanged. The
publisher's late-entry checks remain essential to this pending-edge delivery.

In the 12,000-frame workload, NMI rate rises to 58.26/second from 56.99, but
sampled game ticks fall to 25.20 from 25.90 and picture changes fall to 28.24
from 29.78. No overrun/adapter/SPC fault is detected. The phase audit takes
2530 frames versus the previous 2533 and original 1936, with all four timing
gates still failing. Basic audio/settings gates pass, not full audio fidelity.
This is improved interrupt delivery, **not a demonstrated game-speed win**.

The matched recovery run likewise does not establish improved traversal:
final native camera bytes are 4400 versus the prior 2500 and NES 0000.
Encounter differences remain a confounder; do not promote this experiment as
original speed. Its verified contact sheet/audio is
`build/late-io-recovery-01/site/index.html`, and its baseline phase audit is
`build/late-io-quality-01/site/index.html`. Further reduction of CPU work per
interrupt is needed; increasing delivery alone is insufficient.

The asset-free adapter now also includes the actual generated STA PPUDATA
stub in each replicated bank. Assertion 10 executes it while each of the two
depth guards is separately active, checks preserved A/X/Y/carry, and waits
across VBlank while a hardware interrupt counter must stay zero. Separate
mutants ignoring either guard each fail assertion 10. All existing adapter
positive/negative controls and 49 unit tests pass. Rivalmage is unchanged.

### Specialized PPUDATA writes

Candidate `build/fast-ppudata-01/native-cpu.sfc`, SHA
`7bb5583fb6ca8d17ce21fa5cbc0adaf60040e175deb918ff8668bb72691b2577`,
uses a specialized entry for traced plain STA $2007 instructions. Their
destination is known, so the generated stub only stores the data byte, and
the runtime skips general address dispatch. Indexed writes and all other I/O
retain the existing path. The specialized entry shares the existing buffered
PPU shadow write, address increment, and dirty-row implementation; register
preservation and both interrupt-depth guards remain.

The baseline phase capture takes 2490 frames versus 2530 before this change
and NES 1936. All four transition timing gates still fail; settings pixels and
basic audio gates pass. The verified audit is at
`build/fast-ppudata-quality-01/site/index.html`. The 12,000-frame walk reports
no adapter/SPC fault or graphics overrun, with a maximum observed NMI gap of
41 display frames rather than 49. These workload-dependent gap counts are not
a universal latency bound. Game-counter/picture rates (24.95/26.83 per second)
do not establish a gameplay improvement over the previous run (25.20/28.24),
and black-frame count is higher as scene occupancy diverges.

The executed generated-stub test poisons the unused effective-address mailbox,
writes $A5 to shadow $2010, checks the address advances to $2011, and verifies
queued row state 2 becomes state 3 without losing the staged version. It also
checks registers/carry and both NMI guards. A mutant bypassing the fast write
fails assertion 10. The builder rejects fast mode for reads, indexed writes,
different addresses, and incompatible tail/dynamic modes. All adapter controls
and 52 unit tests pass. This checkpoint does not claim original speed or clean
game audio, and does not deploy to Rivalmage.

### Coalesced PPUMASK preparation

Candidate `build/coalesced-prepare-02/native-cpu.sfc`, SHA
`77b1c87db466e877ab364247966adf6d79b4cc525b0431b106c271d7400bb0ab`,
stores every PPUMASK change but defers producer work when an original NMI is
active or an initialized, NMI-enabled pipeline is running. Both original-NMI
exit adapters already prepare graphics after the game updates. Initial setup
and NMI-disabled loading retain synchronous preparation. This removes redundant
preparation opportunities; it does not skip shadow writes or dirty-row marking.

In the 12,000-frame workload, NMI rate is 59.00/second and the sampled game-tick
rate is 26.17/second, compared with 58.08 and 24.95 for fast-ppudata-01.
Picture changes are 26.47/second; max observed NMI gap remains 41 frames.
No adapter/SPC fault or graphics overrun is detected. The baseline phase audit
is essentially unchanged at 2489 frames versus 2490 and original 1936. All four
transition timing gates still fail; settings pixels/basic audio gates pass.
Its integrity-verified bundle is `build/coalesced-quality-02/site/index.html`.

Per-phase sampled $052B changes also do not show an original-speed result:
NES has 90 changes in each 180-frame idle/walk/attack/resume phase; this native
candidate has 89/86/85/84. These are still diagnostic probes, not a validated
full gameplay clock oracle. The direction-reversal capture completes, but ends
with camera bytes 8E00 versus NES 0000, so traversal remains behind. Encounter
differences confound cross-candidate positional comparisons. Paired media are
at `build/coalesced-recovery-02/site/index.html`.

The asset-free adapter fixture counts producer-bridge calls and checks four
conditions: uninitialized setup, initialized but NMI-disabled loading, running
pipeline, and active NMI. It also checks PPUMASK shadow/register preservation.
A mutant restoring the duplicate pipeline call fails assertion 11. The bridge
is a counter stub in this ABI test; exact renderer pixels remain covered by
the separate graphics harness and game settings audit. All adapter controls
and 52 unit tests pass. No Rivalmage deployment or full-speed claim is made.

### Specialized PPUDATA reads

`build/fast-read-01/native-cpu.sfc`, SHA
`f45f4d5a0cf11965ecc680ac8c3bbb180adf69f6175c3b895214c68d8fcd11b2`,
extends the known-address path to plain LDA $2007. It shares the production
buffered-read/CHR-pointer/palette-bypass/increment body, but omits address
mailbox setup and general I/O dispatch. Indexed and X/Y-register reads remain
on the general path. The generated LDA stub still loads the result after
restoring the caller, setting N/Z from that result while preserving carry.

The baseline capture is only two frames shorter (2487 versus 2489; NES 1936).
Thus dispatch overhead on these reads is not a major measured loading
bottleneck. All four timing gates still fail, while settings/basic audio gates
pass. Bundle integrity verifies at `build/fast-read-quality-01/site/index.html`.
The 12,000-frame workload reports no overrun/adapter/SPC fault, 58.53 NMIs/sec,
25.19 sampled game-counter changes/sec, and maximum observed NMI gap 41 frames.
Whole-run phase differences preclude interpreting these as an overall gain.

Executed assertion 12 poisons the unused address mailbox and checks the old
buffer result, buffer refill, result flags, register preservation, immediate
palette reads, and 1/32-byte increments. A mutant bypassing the fast read fails
that assertion. Depth-guard mutations now change both read/write stub copies;
the executed guarded-access assertion still exercises the write path. All
adapter controls and 52 unit tests pass. Next profiling should
separate actual scene-load CPU work from producer scheduling/backlog rather
than assuming another dispatcher shortcut will remove the remaining stalls.
Rivalmage is unchanged.

### Grouped attribute conversion and load-queue evidence

The baseline capture now records counts of all four row states, queued CHR
jobs, and original $010B ticks. In `build/load-queues-01`, settings takes 158
frames and story 156; only 21/20 of those frames have entirely clean row/CHR
queues. Up to 96 rows are pending. This identifies conversion/backlog as a
material part of loading, but does not isolate every original game wait.

The producer now computes attribute-row/quadrant selection once per four-tile
group and palette bits once per tile pair, rather than recomputing and looping
over shifts for every tile. Source/destination indices advance directly. The
two-row production budget, immutable staged-row states, and VBlank consumer
limits remain unchanged.

Retained candidate `build/grouped-rows-01/native-cpu.sfc`, SHA
`f3b915a75ad3532c175afded05163703936b62307ec3f9a3886ef9a30ebe751a`,
completes 12,000 frames without detected adapter/SPC fault or graphics overrun.
The sampled game-tick rate is 28.11/second versus fast-read-01's 25.19. Baseline
capture length barely changes (2485 versus 2487; NES 1936); all four timing
gates still fail. Settings pixels and basic audio gates pass. The verified
bundle is `build/grouped-quality-01/site/index.html`. This is not original-speed
or audio-fidelity certification.

An additional four-row menu-budget experiment (`grouped-rows-02`, SHA
`73827395501657f486ad2d4953ac380fa809b5360d3adf16a1505732ee38363c`)
reduced capture length to 2378 but failed settings pixels: lower text was
missing at the audit checkpoint. The budget change was removed, not accepted
as a performance win. Its evidence remains in `build/grouped-quality-02`.

`tools/check_rows.py` executes the production converter on prescribed distinct
data in all four nametables, then checks all 3840 visible tiles and unused
rows against an independent Python attribute oracle, in both pattern halves.
It verifies the source fixture itself, not merely output derived from whatever
RAM happened to contain. A wrong vertical-quadrant mutant fails. CI runs this
test alongside the existing rendered-pixel and late-entry controls. Fifty-four
unit tests pass. No hardware deployment was performed.
