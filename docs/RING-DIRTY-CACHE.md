# Faster ring copies do not yet fix the retained interrupt

Two new offline candidates preserve PPU data and pass low-level comparisons,
but neither recovers the remaining saved-state combat stall. Keep phase96
candidate2769 as the timing baseline. Rival remains on harmonic splash2648;
no hardware input, reset, upload or OBS change occurred during this work.

[Executed comparisons, replay collages and native audio](http://127.0.0.1:8766/ring-dirty-review-2828/).

## Changes

- Combined-cache2807, SHA
  `328c06e50c3ac577b22dbeeb4fbc8db272b99cc71c1b442b3c2ece214604c687`,
  caches the physical pointer for both linear and stride32 nametable commands.
  It coalesces linear dirty marking within an eight-byte group and specializes
  tile-row alias marking. The borrowed DP byte is saved/restored. A512-byte
  helper occupies verified unused$6900 space in each of the eight mirrors.
- Tile-only2814, SHA
  `ebcb00058e584bf0c1adf80dd68526b1d042d2a5fbbefb47ba1cc10fceb3f58d`,
  combines the previously tested stride32 pointer cache with the specialized
  tile marker only. Linear writes retain the old loop. Its helper is256 bytes.

Both admit only binary arithmetic, counts1..32 and logical nametable starts
$2000..$3AFF. Attribute writes retain the original dirty marker; unsupported,
zero-as256, long, CHR, palette and decimal cases retain the original copy.
All writes, unchanged-byte comparisons, mirrored dirty flags, logical address,
ring wrap and write counts remain. These are not command-budget reductions.
Only eight entry trampolines, eight helper areas and checksum change; no
graphics, controller, game timer or SPC payload changes.

## Executed memory and clock checks

Oracles2808/2815 each execute217 parent/candidate fixture pairs from actual
cartridge bytes without relinking the runtime. Each compares all128KiB WRAM,
including PPU shadow, DP scratch, game data and saved A/B/P/X/Y/D/DB/SP.
Only dead stack and the fixture heartbeat are excluded. Each also passes180
independent CIRAM/dirty/counter/ABI checks. These fixtures have NMI ownership
set; they are not an interrupt-injection proof.

Each wrong-stride mutant fails. Additional executed controls2824 reject wrong
vertical and horizontal aliasing, a lost dirty flag, missing shadow store and
missing write accounting. No corrupted binary is deployed.

Neutral same-core instruction measurements2810/2822 execute exact oracle ROMs:

|20-byte stride32 call|Parent2769|Combined2807|Tile-only2814|
|---|---:|---:|---:|
|$2000|44,214|28,352|28,224|
|$20FF, page crossing|44,446|29,076|28,948|

Units are elapsed master clocks from entry through caller return, including
emulated intervening events. Tile-only saves34.9–36.2% on these calls, not on
the entire game. The broader linear-cache variant can add bookkeeping to
unchanged writes; no linear speedup is asserted.

## Same-state proof: still fails

Checkpoint2797 and passing same-ROM control2802 are reused at frame2234.
Both replay wrappers rebuild the exact candidate from2769 before accepting
cross-ROM state, reject PCs inside the patched path, require equal initial
full WRAM/all registers and replay actual P0/P1 callbacks. The original90-frame
comparison and all later differences remain in reports2809/2816.

- Combined2807 loses the earlier native advance at2237. Although its counter
  advances at2239, completion remains at2240 and the picture differs at2238.
  This moved failure is **not** recovery of the target stall. A new unit test
  explicitly rejects that misleading interpretation.
- Tile-only2814 preserves pictures and PCM through2241 in this replay, but
  native NMI still fails to advance at2239 and completion still occurs2240.
  Cross-ROM differences thereafter remain; it is not called neutral.

The first2809 invocation used the wrong checkpoint directory name and failed
before execution/output creation. The successful retry uses the actual
`phase-balance-checkpoint-2797` source. No evidence was discarded or rewritten.

## Fresh-boot combat and interrupt costs

Campaigns2811/2818 both finish4928 frames. Each observed run matches its
same-core normal full timeline, PCM and actual two-port inputs. The strict
combat result fails, and the busy-NMI-inclusive summary retains1751 two-frame
intervals plus one three-frame interval2236→2239 with busy frame2237.
Independent encounters are not matched-work speed ratios.

Instruction windows2817/2821 are neutral against their own controls2813/2820.
The longest retained original interrupt in the targeted window is:

|Build|Original NMI entry|Original body return|Elapsed clocks|
|---|---|---|---:|
|Parent2769|2238 line228 cycle316|2239 line20 cycle342|73,678|
|Combined2807|2237 line222 cycle442|2238 line7 cycle1280|64,946|
|Tile-only2814|2237 line218 cycle196|2238 line2 cycle688|63,236|

These fresh-boot traces locate the remaining overrun; their differences are
not a matched-state cycle comparison. The independent exact-state test above
still fails. Entering earlier and doing fewer copies does not help if the
masked path still covers the full VBlank and discards its event.

The remaining tail also repeatedly enters the generic adapter for PPUADDR,
PPUSCROLL/PPUCTRL and mapper writes. This is a concrete next cost target:
preserve each write and complete ABI while eliminating redundant adapter
setup, then repeat the same saved-state recovery test. A correctly accounted
queued-interrupt design remains an alternative; do not fabricate a game tick
or hide the failure by excluding the NMI-busy frame.

## Traversal and actual scrolling: do not promote

Both routes2812/2819 complete8941 frames. Tile renderer2823 exactly matches
the normal full timeline and PCM. Audit2826 checks7342 complete eligible frames
and6382 held-camera frames, with zero missing coverage, splits or stale-camera
failures. This does **not** imply smooth camera pacing:

- East sweep:207 two-frame holds, eight14-frame holds, no short irregular hold.
- West sweep:one1-frame,146 two-frame, one3-frame and seven14-frame holds.

Thus tile-only introduces two short irregular westbound holds relative to
the qualified2769 route. All long encounter stops remain included. Neither
new candidate has fresh full menu, main-to-display latency, DSP or physical
qualification; none is claimed. Native saved-state audio is supplied for
audit without normalization or a pop-free verdict.

## Tests

1,200 tests pass (`/tmp/rcr-tests-2825.log`), including new mirror/patch scope,
mutation-preimage and moved-miss rejection tests. `git diff --check` is clean.
Review2828 verifies166 source bindings,16 published artifacts and three exact
native audio copies. Its browser-rendered comparison collage was inspected.
The goal remains open: exact original-speed parity, physical scrolling and
sporadic gameplay audio transients are not resolved by these local savings.
