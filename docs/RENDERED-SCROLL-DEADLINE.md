# Two real missed street-scroll deadlines, not map corruption

Candidate 373 remains **experimental and not deployed**. Its original
`hidden-sprite-background-audit-383` failure is unchanged. No screenshots,
sample selection, game state, timeouts or acceptance thresholds were adjusted.

`build/render-scroll-audit-386/index.html` diagnoses the exact two failing
samples using the actual renderer, plus an independent CPU timing replay:

| Park camera | NES frame / displayed scroll | SNES frame | SNES lines 32–158 | SNES lines 159–191 | Camera hook enters |
| --- | --- | --- | --- | --- | --- |
| 255 | 8398 / 255 throughout | 7748 | 253 | 255 | line 35, cycle 604 |
| 371 | 8244 / 371 throughout | 8268 | 375 | 371 | line 47, cycle 1322 |

The camera calculation reaches `camera_deferred_nmi_exit` **after** HDMA has
consumed the street scroll at line 32. Updating the live table cannot change
that already-used value. Its second street entry, consumed at line 159,
sees the new value and creates the observed horizontal split. Frame-end RAM
and HDMA-table values are correct in both cases; that earlier telemetry was
insufficient to certify on-time display. The full-line observation also
explains why a single global four-pixel alignment did not explain the whole
second image. This diagnosis does not certify that all map data is correct.

## Evidence and noninterference

- `render-scroll-nes-384`: 8,548 frames, complete. Every timeline field and
  PCM sample equals pinned normal `park-single-nes-331`.
- `render-scroll-snes-384`: 9,953 frames, same death/respawn and timeout.
  Every timeline field and PCM sample equals `hidden-sprite-single-normal-382`.
- `render-scroll-spans-385`: a second 9,953-frame replay with the existing
  linked-PC/span observer. Again all normal timeline fields and PCM match.
- The audit binds capture receipts, core/ROM hashes, renderer traces, observer
  source, linked timing metadata and the pre-existing failed report. It
  rejects missing/duplicate scanline samples and unsupported rendering state.
- 435 Python tests pass, including all 512 scroll positions across 32 NES
  pixel groups, shifter provenance rejection and split-line preservation.

The NES observer records both actual tile-fetch addresses in the two-tile
pixel shifter and the fine-X value used to emit each eight-pixel group.
Address continuity is checked before deriving its displayed scroll.
The SNES observer records the real `LineData` offsets at renderer flush.
Each new hook writes host diagnostics only: no emulated RAM/register writes,
timing changes, pixel modification or replacement inputs.

## Reproduce without invalidating historical observers

The historical background observer source hashes remain unchanged. New hooks
live in **separate source copies** `.deps/fceumm-raster` and
`.deps/snes9x-raster`, created from the existing diagnostic source trees.
Integration patches are `tools/fceumm-raster-scroll.patch` and
`tools/snes9x-raster-scroll.patch`; apply inside the respective copy with
`git apply --unidiff-zero`. Reverse-application checks pass. Build separate
targets with `make -j4 TARGET_NAME=rcr_raster` (SNES from `libretro/`). Never
overwrite the pinned normal or background cores. The first NES compilation
failed for a missing stdio include; both diagnostic cores built successfully
after that correction.

Set `RCR_RENDER_SCROLL_TRACE` to the capture directory name plus `.csv`.
The default trace window is frames 7600–8420; optional `RCR_RENDER_FIRST` and
`RCR_RENDER_LAST` override it. Run the unchanged `traversal-park-single-sweep`
scenario with frame images, and PPU telemetry on NES. Do not enable background
telemetry on these new cores: their purpose is supplemental scroll provenance,
not replacing the separately qualified background observer.

`capture_park_spans.py` now accepts `--scenario traversal-park-single-sweep`;
its previous default remains unchanged. Replay with the pinned span/ACK core,
candidate 373 and window 7700–8300. Run `python3 -m tools.audit_render_scroll`
with those captures, their normal baselines, failed report 383, and
`--spans build/render-scroll-spans-385` into a fresh output directory.

## Next implementation target

Reduce or correctly schedule work **before the original camera calculation**
so the real street entry is ready before line 32. Merely writing `$210D`
afterward, changing the line-159 entry, or checking frame-end table equality
would leave an already-drawn stale portion. Keep the strict failed-image
gate and the ordinary controller-only route. First-room load speed,
combat/endurance and physical gameplay audio remain open. No Rival restart
was performed for this diagnostic-only change.
