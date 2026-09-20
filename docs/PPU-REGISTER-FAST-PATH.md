# Common PPU-register writes: measured savings, incomplete interrupt fix

[Web review: saved-state collages, clock measurements, native audio and failures](http://127.0.0.1:8766/ppu-register-review-2867/).

No Rival upload, reset, input or OBS change. Hardware remains on2648. Neither
new candidate is promoted; phase96 build2769 remains the qualified offline
timing baseline. Original-speed parity and pop-free gameplay audio remain open.

## Implementation

The generic write adapter saves X/Y/D and sets DP$1B00 before decoding every
PPU write. PPUCTRL, OAMADDR, PPUSCROLL and PPUADDR can perform the same updates
with absolute WRAM addressing. New helper `snes/ppu_register_fast.asm` preserves
A/P/X/Y/D/DB/SP and the legacy hidden accumulator B=$1B. It preserves CHR dirty
bit decisions, the scroll/address latch, source mailboxes and interrupt masking.
Unsupported destinations retain the original dispatcher. No new RAM, graphics,
game timers, controls or SPC data are introduced.

The first candidate2833 globally hooks the dispatcher;2834 adds ring-tile2814.
That also charges classification overhead to unrelated I/O. The targeted
follow-ups change only the JSL destinations in18 known non-indexed PPU-write
stubs,144 mirrored calls total, plus eight256-byte helpers and checksum:

|Candidate|Parent|ROM SHA256|
|---|---|---|
|Targeted write-only2849|2769|`34ef96ac509156eea2aa25cc7e6bbfaf82645d671dddd042acb448abdee28288`|
|Targeted write + tile2850|2814|`0d1153273d4e0868fa4dfbcadaf7c7c8a8703a8c473e68db8ae15b6c34ce57a6`|

Generic dispatch, mapper/audio writes, indexed writes and existing stub
epilogues/coroutine continuations are unchanged in the targeted variants.
The builder verifies each mirrored call's complete preimage and constrains
every changed byte. Helpers occupy verified FF-filled$7000..$70FF space.

## Executed checks and limitations

Actual-cartridge oracles2835/2838 each pass222 complete-WRAM comparisons and
198 independent register/ABI checks. Extra oracle2842 adds48 comparisons and
independent checks for unchanged CHR-control bits, extreme scroll latches,
decimal flags and additional stack positions. Total helper coverage:270
comparisons,246 independent checks. All eight runtime banks are exercised
using their own production bytes, not copies of bank1. Only dead stack and
fixture heartbeat bytes are excluded from the128KiB comparison.

Four executed mutants fail: wrong high-address mask, lost CHR dirtiness,
incorrect scroll toggle and lost hidden B. Proofs2857/2858 rebuild each entire
targeted ROM, bind all helper/fallback bytes to the executed qualified image,
and verify all fixture artifacts. This inherits helper execution by exact
identity; it does not separately execute every original coroutine return.

Exploratory fixture2830 fails on the **unmodified parent** at SP0. Debug2832
also fails to return at SP1/2 and records DP0000 instead of1234 at SP7/8;
SP3/4/5/6/9/24/64 return the expected ABI. These boundary failures remain
retained, not converted into passing cases. The qualified matrix explicitly
uses selected safe long-call/word-stack positions; it is not an unrestricted
stack-wrap guarantee or proof of a failure in ordinary gameplay. NMI ownership
is preset in the fixture; no injected-interrupt proof is claimed.

Prototype2829 and source-preflight-tightened2833 have the same cartridge hash.
Only2833 has the current builder-source binding. The fixture's header and
failure-log handling were corrected before the passing2835 run. Inherited
reports and failed artifacts were not overwritten.

## Measured dispatcher cost

Timing2843 executes the exact oracle cartridges in fresh processes, with
same-core full-RAM equality between normal and instruction-observed runs.
Five calls from dispatcher entry through caller return:

|Write|Old clocks|Fast clocks|Saved|
|---|---:|---:|---:|
|PPUCTRL, changed CHR bits|740|536|204|
|OAMADDR|666|446|220|
|PPUSCROLL|808|598|210|
|PPUADDR, high latch|844|582|262|
|PPUADDR, low latch|826|546|280|

These are elapsed master clocks for specific FastROM fixture calls:26–34%
less per call, **not** a whole-game speedup percentage. The outer translated
stub still saves/restores registers, fills mailboxes and applies its original
NMI-enable policy.

## Same-state failure remains

The frame2234 checkpoint is inside the changed dispatcher region, so both
initial replay attempts2836/2837 reject before execution. New checkpoint2839
captures2232/2233 without changing the entire4929-frame reference timeline,
PCM or two-port input stream. At2233 the CPU is at the native NMI entry.
Control2844 reproduces all90 resumed frames exactly.

Replays2845/2846 (global) and2851/2852 (targeted) require identical initial
128KiB WRAM/all CPU registers, actual P0/P1 inputs and the exact freshly rebuilt
patch composition. **All four still miss the native advance at2239 and finish
the affected game update on2240.** Pictures match through2240; earlier PCM
and later state differences remain recorded. A faster local routine is not
called a recovered frame.

## Independent combat: one promising pass, not causal recovery

Both targeted running/jumping campaigns are normal/observer-neutral for every
timeline row, native PCM sample and actual controller callback:

- Write-only2853:4928 frames; busy-NMI-inclusive1751 two-frame intervals plus
  one three-frame interval2236→2239. Strict combat fails.
- Write + tile2854:4927 frames;1753 two-frame intervals and no off-cadence
  stable intervals. Strict combat passes; its other/censored iteration
  categories remain in the full report.

Fresh-boot encounters differ. This passing campaign cannot supersede the
failing exact-state comparison or establish matched NES workload parity.
Instruction window2865 is neutral against2861. It observes a retained original
body from2236 line213/cycle496 to line258/cycle858 (61,738 clocks), followed by
another original NMI at line261. In this fresh run the edge is serviced before
it disappears; that is not the same initial state as the failing replay.

## Actual scrolling

Both full routes finish. Renderer observations match their own normal complete
timelines and PCM. Audits2863/2864 find no missing coverage, split camera or
extra-frame stale-camera failures across7618/7342 eligible frames respectively.
Actual pacing gives a different result:

|Candidate|East uniform-endpoint holds|West uniform-endpoint holds|
|---|---|---|
|Write-only2849,9224-frame route|211×2,10×14|150×2,3×14|
|Write + tile2850,8940-frame route|207×2,8×14|1×1,146×2,1×3,7×14|

The combined candidate retains two short irregular westbound holds. Long
encounter stops are included. Write-only keeps steady pacing in this replay
but still fails combat. Neither has fresh full menu, DSP, main-to-display
latency or physical qualification; no such pass is inferred from unchanged
graphics/audio assets. Review audio is exact unnormalized saved-state PCM,
not a pop-free or waveform-fidelity assessment.

## Tests and next work

1,203 tests pass (`/tmp/rcr-tests-2862.log`). New tests constrain both patch
scopes, reject differing mirrors/reapplication, ensure unrelated I/O remains
untouched and independently reject dirty/ABI corruption. `git diff --check`
is clean.
Review2867 verifies179 source bindings,16 published artifacts and three exact
native audio copies. Its rendered comparison collage was visually inspected.

Preserve2769 and these default-off savings. The next useful optimization is
the remaining duplicated outer-stub/inner-handler work, with complete original
stub and coroutine ABI tests—not another blanket phase delay. More generally,
the interrupt design must conserve a real VBlank event even when retained work
crosses it. Any queued-event implementation must prove acknowledgment, exact
once-only delivery, original audio-driver order and safe DMA timing; advancing
a software counter alone is not a fix. The known saved-state stall, camera
pacing and physical audio remain required gates before a Rival handoff.
