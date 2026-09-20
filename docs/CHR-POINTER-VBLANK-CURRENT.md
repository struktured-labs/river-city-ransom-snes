# First NES-speed room load; skipped camera publication fixed experimentally

Current experimental cartridge: `build/camera-first-590/native-cpu.sfc`.
SHA256 `b319afd1069370737b9e9940a5b3e2cabe6956195c4cadf64a5307a648e20aeb`.
No Rival deployment/reset. Original-speed gameplay, full scroll latency and
audible/physical audio gates remain open. No original game graphics changed.

## Persistent CHR pointer

The paired compressed-data reader now uses a persistent physical pointer
instead of copying its high byte and bank on every pair. Cache validation is
shared with generic reads: page identity, valid bit and all mapper/bank-restore
invalidations are retained. Binary/increment-one/CHR/page-boundary guards and
the scalar fallback remain intact. Public read helpers retain their ABI.

Cache storage is now `$1B50` valid, `$1B51` page, `$1B54..56` long pointer.
The paired reader sets the low byte before each pair; generic reads copy the
validated high/bank into their existing pointer. Former `$1B52..53` locations
are no longer used by the cache. The masked paired-read critical section is
unchanged. No arbitrary decimal-state or pending-interrupt proof is claimed.

Candidate582 isolated this improvement, SHA256
`1696b846aae0d97c33642e2b6124687aaf7dd441cdd92381592878dbe927aaed`.
The fresh disabled early-camera control590 reproduces it byte-for-byte.

`chr-pointer-cost-587` is a complete, neutral 9,407-frame CPU-observed replay.
During first-room rendering-off, reader + buffer + generic pointer + CHR
resolver own elapsed clocks fall from932,828 (539) to854,140 (582), an8.4%
reduction in those selected nonoverlapping regions, not overall game speed.
The intermediate redundant-guard-only experiment578 measured886,258 and
still loaded in21 frames. Persistent pointer582 reaches20.

Fresh current-source matrices595 execute256 cartridges: paired off/on crossed
with cache off/on, all32 pages and both inversion modes, bank-value and
adapter-ABI checks plus boundary/nametable/palette cases. Each rejects six
cache mutants. `camera-first-chr-oracle-596` rejects eight additional reader
and persistent-pointer mutants. Removing either physical pointer store fails
the initial public-read case2, before the later paired-read case13; the test
expects that specific earlier failure. Initial wrapper runs583/587 failed
because they expected case13, not because a corrupt cartridge passed.

## Camera failure: skipped final batch also skipped the camera

The faster582 build exposed a concrete park regression in the unchanged
background sweep: room3/camera248, SNES frame8485 versus NES frame7612.
Its fixed background playfield differed by6,847 pixels. Camera248 was already
committed during8484, but live/rendered camera250 remained for8485.

Neutral CPU capture589 shows the VBlank publisher reaching `final_room` at
line255 in8484. Its timing guard correctly refuses the final OAM/palette
batch; however, the old camera-table update was after that same guard.
There were no publisher writes to the street camera table that VBlank.
This is not a late-frame telemetry inference: all160 renderer lines display
the old position in8485.

New default-off `experimental_camera_vblank_commit` requires safe camera
publication. After the existing entry-time VBlank guard accepts the call,
the publisher copies the four committed street-camera bytes before draining
graphics. It only does this for visible gameplay, not transitions or other
tasks. HDMA descriptors/MMIO, VRAM/OAM/CGRAM transfers and their existing
guards remain unchanged. The camera hook's mid-screen anti-tearing guard
remains enabled. The feature does not wait or add/remove an original game tick.

Neutral CPU capture595 shows both low-byte writes at line240 of8484, before
the same line255 final-batch refusal. The complete next-frame street renders
248. `camera-first-case-597` binds this specific before/after counterexample
to instruction, cartridge, normal-core and renderer hashes; it is not a
general camera-latency pass.

`camera-first-oracle-593` executes the complete production publisher, not
only an extracted copy helper. A real2KiB CHR DMA forces final-batch refusal.
Nine cases cover enabled/disabled behavior, task/transition guards and
active/late/high-bit beam rejection. Both camera entries, adjacent
descriptors, CHR ownership and DP/DB/stack are checked. Four actual broken
cartridges are rejected: missing low/high copy and ignored task/transition
guards. Initial fixture592 incorrectly saved snapshots through unmapped
bank00 addresses;593 fixes the fixture with explicit bank7E stores.

## Fresh current-cartridge gates

All500 Python tests pass. No acceptance threshold was relaxed.

| Room | NES room-change to first visible | Candidate590 |
| --- | ---: | ---: |
|1|20|20|
|2|31|28|
|3|30|29|

Entry593 passes all three no-later visibility gates, but still fails exact
fixed-offset fade images: room2 first appears at offset6 instead of7 from
rendering enable. This is a loading milestone, not a full-speed certificate.

- Full adaptive captures591:8,629 frames, normal/background/renderer neutral.
  Background audit593: all775 samples exact, coverage259/103/110/303. Parent
  had one mismatch at248; current has none.804 frame-end publication warnings
  and four settling comparisons still fail. Those warnings include camera
  computed after rendering and are not individually proven missed deadlines.
- Split audit593: zero splits across7,314 eligible frames /1,170,240 actual
  lines.842 frame-end camera differences remain explicitly recorded. The
  known broken renderer control still fails.
- Status audit596: first Present Status entry and reopen both pixel-exact.
- Full fixed audio capture594:9,407 frames neutral to normal591. Provenance596
  verifies all212,405 actual SPC receive stores across9,235 paired packets,
  with zero mismatches; key-on/ready checks pass, processing161–1169 ticks.
  PCM is not identical to582; only each observer's own normal-core equality
  is asserted. No pop-free, bass-drop or physical-audio claim.
- Park audit596: no stable packet interval above1.5 frames. Neutral596:
  no late NMI interval in7600..8420. These remain scoped observations.

Next: retain the loading improvement and independently scheduled camera
commit while investigating remaining genuine deadlines, fade timing and
audio fidelity. Current experiments remain opt-in; no hardware restart.

Review: `http://127.0.0.1:8766/camera-first-review-598/`.
