# Current early-OAM tail elision, experimental3955

ROM SHA256 `f6f69215716ecc077c9082da0a20db1eaaa064daab81b0992a54cade834d1e16`.
Exact3934 parent; not promoted or deployed. Speed/scrolling/audio remain open.

Follow-up: [fresh broader graphics qualification and remaining gates](EARLY-OAM-LIVE-HALF-QUALIFICATION.md).

## Mechanism and rationale

The failing3934 dialogue window spends a full544-byte OAM transfer before its
row search. The current delta sprite producer updates64 live SNES slots
(256bytes); its unused slots and high table are initialized once and remain
static in visible gameplay. Source inspection locates that initialization in
`snes/sprite_delta.inc`; current early publisher is the guarded42-byte helper
atC07300. Private latch1BF0 has no other named production user and is cleared
by the existing full-WRAM reset. This assumption needs continued full-route
hardware-memory observation; a future extra-sprite/high-table writer must
invalidate or revise it.

An older disabled live-half experiment had local correctness tests but failed
its old gameplay scheduling checks. It is not inherited as current approval.
The new66-byte helper atC05100 uses the same selection/completion macros, but
keeps every hidden-transition upload full as well as the first upload. Later
visible uploads send256bytes. The completion latch is written only after DMA.
Original exit A=$80, X=544 and Y are retained, as is VMAIN=$80.

Only the first three bytes at7300 (JMP5100), verified free helper space and ROM
checksum change. SPC engine, original graphics, input, row/CHR/palette guards
and publication byte budgets are unchanged. No scanner optimization was made:
the measured transfer cost was the larger available saving.

## Executed checks

-3956 runs the exact emitted helper in an actual emulated SNES. Physical OAM
 starts poisoned;256 generations change all live bytes. Four hidden generations
 also change the tail. All544 physical bytes are checked after every upload.
 A1T advancement checks the actual256/544-byte size, not just the helper's
 selection. Wrong source, missing completion latch, missing DMA, short hidden
 transfer and always-full mutants all fail. This fixture starts hidden.
-3960 freshly exercises the shared production macros with an initially visible
 full upload, then255 changed live generations, against a full-upload control:
512 generations and four rejected mutants. It does not replace the current
 helper's separate executed test.
-Three patch tests pass0.089s: exact changed-byte extent/SPC preservation,
 every overwritten guard/free byte mutation, and repeat-application rejection.
-Actual game sprite window1978–2020: normal3964 and observed3965 are exactly
 neutral across the2,099-frame prefix, including native PCM. All43 uploads
 are256bytes, but **all544 physical OAM bytes** match the complete staged
 image after each upload. All239 scanlines/frame are covered. All20 known
 source generations render next frame; initial source/display are censored.
 Recorded stale-untransferred-tail and missing-render-span mutations fail.
 Replays5.290/5.307s. This is one43-frame gameplay window, not all scenes.

## Measured user-visible improvement

Text observation3958 preserves the full9,090-frame same-core primary timeline
and native PCM against normal3957. It takes31.376s and retains84 snapshots.
The original dialogue tileE8 at row25/column12 has identical source5989 and
prepared5990 in parent/trial. Actual VRAM becomes current at5991 instead of
5992. No comparable text word is later and original sources match throughout
the sampled windows. An unsupported playfield word at8236 remains in the strict
failed gate (prepared/source0D, parentVRAM0C, trial0D); no waiver.

Neutral instruction3963 covers5989–5991,22.877s replay. At5990 the full early-OAM
helper (entry7300 through beforeRTS, including trial trampoline) falls from
4,850 to2,652 elapsed master clocks:2,198 saved in this invocation. DMA-trigger
to next instruction is4,562 versus2,138 clocks at different beam phases. These
are measured elapsed intervals including emulated events, not exclusive DMA
cycle counts or a whole-game speed percentage.

Trial visible dialogue25 transfers at5990 line252/cycle342. Its alias89 gate
is later rejected; the ready mirror is retained, not fabricated complete.
The queue's longer-term mirror latency remains a broader qualification item.

Across the normal9,090-frame route all original counters and requested/delivered
inputs match3934. There are55 changed pictures and two changed logical-camera
samples, all retained. ALEX's source-phase difference from3890 is not resolved
by comparison with3934. No original-NES timing or complete graphics claim.

## Audio tradeoff and remaining gates

Full observed3961 is same-core timeline/native-PCM neutral. Audit3962 keeps
8,641 packets,1,588 restart checks,4,846,034 stereo sample frames, peak6336,
maximum adjacent step4556 and zero clipping. Stable packet range is
12.148–20.858ms versus3934's12.226–20.858ms: maximum unchanged, minimum shorter.
All7,342 classified and1,298 excluded intervals remain. Stable-room measured
game-loop populations598/1746/477/847 remain two frames each. Analysis27.705s.
This does not establish pop-free audio or original-speed equivalence.

Two-player combat3967 and review3968 complete both4,930-frame policies with
same-core neutral observations:1,752 sustained-attack and1,709 running-jump
intervals are all two frames, with no off-cadence interval or adapter fault.
This is not a matched original-NES encounter benchmark. Both camera differences
versus3934 (2426:0→65532,5979:65532→0) have identical rendered pictures in their
respective frames; the internal-state cause remains unresolved.

General DMA/renderer,
palette/menu coverage, full-route static-tail integrity, remaining source-phase
differences and physical SNES Junior/EverDrive acceptance remain open. No
hardware/OBS action or default release change.

- [All55 changed pictures, exact costs, physical OAM checks](http://127.0.0.1:8766/early-oam-live-half-review-3966/)
- [Native full-route audio](http://127.0.0.1:8766/early-oam-live-half-audio-review-3962/)
- [All text-window records](http://127.0.0.1:8766/early-oam-live-half-text-review-3959/report.json)
- [Fresh two-player combat](http://127.0.0.1:8766/early-oam-live-half-combat-review-3968/)

Review3966 was generated before combat completed. Its phrase “audio remains
non-pop-free” means pop-free acceptance is unverified, not a listening result
or proof that this exact cartridge has audible pops. Native measurements alone
do not establish that claim in either direction.
