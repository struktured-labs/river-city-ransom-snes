# Transition and NPC/shop graphics investigation

## Per-frame evidence

`benchmark_capture.py --frame-images` optionally retains every video callback
as a PNG. Each timeline row binds the PNG hash and the existing raw RGB pixel
hash. `tools/frame_audit.py` verifies the source capture, exact frame-number
path, PNG hash and decoded pixel hash before making a contact sheet. Selection
is explicit; there is no visual alignment or automatic quality pass.

The deployed triangle-corrected ROM's baseline is captured in
`build/transition-frames-01/snes`. All 2,035 records match the existing fields
of `build/game-ack-01/snes/timeline.json`, showing that retaining images did
not perturb the run. The contact sheet is
`build/transition-frames-01/street-audit/index.html`.

Frame 1000 visibly has scrambled horizontal background strips across the
street. At that frame PPUMASK is $18, CHR jobs are empty, but 32 rows remain
dirty and 21 prepared rows await publication. This is evidence of premature
display of an incomplete background, not proof that CHR upload alone causes
the loading corruption. A transition presentation guard remains to implement
and test; this capture work does not itself hide or fix it.

Separate read-only OBS captures preserved the user's live Rival reports:

- `build/rival-mall-paused-01.png`: two scrambled NPCs, intact Alex/storefront.
- `build/rival-shop-01.png`: missing shop-panel text, incorrect colors and
  stray character pixels; includes a MiSTer screenshot notification.
- `build/rival-shop-02.png`: later view, notification cleared, center black.

No control inputs, reloads, OBS scene changes or recording changes were sent.
The second shop image is not assumed to show the same game state. These live
images are not yet a deterministic local mall/shop reproduction.

## Mapper correction and its limits

The producer lacked MMC3 CHR inversion, although the CPU-side CHR reader
implemented it. `native_prepare.asm` now XORs the source slot with four when
mapper-select bit 7 is set, while retaining the physical PPU destination.
This follows the pinned original core's `FixMMC3CHR` in
`.deps/fceumm/src/boards/mmc3.c`: its bank-register groups swap $0000/$1000.

Executed video case 9 uses distinct R0..R5 values and odd R0/R1 inputs. It
checks all four BG slots and all four OBJ slots before and after a live
inversion-only change. Suppressing the XOR fails case 9. Existing exact-pixel,
scroll, cache, late-entry, last-CHR-slot and clipping controls also pass.

Candidate `build/chr-inversion-01/native-cpu.sfc` SHA:
`765aca04a25d1f92d5f4f8a8b06d5c04c1a21c55c086173de01ef3e6eb006047`.
Its baseline remains 2,029 frames, with the same four speed gates failing and
the scoped pixel gates passing. No deployment was made.

The 5,605-frame `build/chr-inversion-traversal-01/snes` records mapper-select
and CHR registers as well as every frame image. At every sampled frame
boundary, CHR inversion and 8x16 sprite mode are both off. The traversal
remains near the trash-pickup area and does not reproduce the mall/shop scene.
Therefore this correction is **not claimed to fix the reported NPC or shop
corruption**. Frame-boundary sampling also cannot exclude brief intermediate
mapper changes. Exact mall/shop routing and per-scene comparison remain next.

All 78 unit tests pass, including corrupt PNG/raw-pixel bindings and invalid
frame paths. Title branding is assigned separately at the user's request;
it must not weaken these graphics or speed checks.
