# Early OAM: restore live graphics-pattern uploads

Experimental candidate3527, SHA256
`635f21cd2f7951dd3e8acf07fabfb8acdc68302518f1bdb942a3a3fd8d4c71e3`.
No default change, deployment, MiSTer action or OBS action.

## Cause and actual correction

While investigating the remaining five-frame health-tile latency, the full DMA
trace exposed a more important problem: candidate3502 has **zero visible CHR
uploads**. Moving544-byte OAM DMA earlier consumes over three scanlines before
the old CHR admission cutoff243. Pending jobs cannot enter, even though their
transfers would fit after moving the sprite work out of the final batch.

3502 leaves two jobs pending from frame2424 through5936:3,513 visible frames,
ending only at another transition. Safe completed DMA envelopes did not prove
queue liveness. Earlier3502 renderer/DMA passes remain valid only for their
stated limited scope; they do not qualify its graphics content for deployment.

`tools/early_oam_chr_slack.py` changes only the CHR preflight operand243→246
and cartridge checksum, on exact3502. Row249 and palette254 guards, original
graphics bytes, SPC engine and controller code are unchanged. The three
observed visible2048-byte CHR transfers begin at line246 after preflight and
finish at258. Full-DMA safety remains independently mandatory.

## Regression proof

[Browser collage and native audio](http://127.0.0.1:8766/chr-starvation-published-3546/)
links [detailed immutable evidence](http://127.0.0.1:8766/chr-starvation-review-3544/report.json).
The detailed report validates1,377 source bindings. The publication wrapper
copies only reviewed images/HTML and byte-identical WAV into the existing
restricted evidence root; no server security rule was relaxed.

Same-core fresh prefix captures retain raw WRAM and actual VRAM at every frame
2390–2450, without state restoration or game-memory edits. Normal and observed
full prefix video, input, state and native PCM are identical. The snapshot
replays take6.63/6.67seconds for parent/candidate.

| Job | Source frame | Source-equal VRAM frame | Corrected stale bytes |
| --- | ---: | ---: | ---: |
|18, ROM CD2000 → VRAM A800 |2424 |2426 |197 |
|20, ROM CD4800 → VRAM B000 |2424 |2427 |54 |

The previous build never publishes either job in the observed window. A mutant
that simply clears the job flags while leaving stale VRAM is rejected. All
other observed jobs and initial/terminal censoring are retained. Exact-frame
screenshots2428/2450 show63/73 changed pixels on NPC sprites; assets are not
redrawn. Full-route visible pending spans shrink from3,513frames to a maximum
of3; both new spans end by actual clearance rather than becoming hidden.

Current3527 qualification:

- 9,089-frame route, same-core observer-neutral full primary video/state/input
 and native PCM.7,476eligible renderer frames: no missing coverage, splits or
 stale-camera failures.
- 52,695 safe complete general-DMA envelopes, latest visible end259; three live
 CHR uploads observed. HDMA and per-byte physical validation remain separate.
- 21 source-cohort sprite generations rendered next frame, with follow-through
 and all later/censored sources retained.
- 8,641 sound commands,1,585 restarts, all64 startup phases, no tested first
 pitch/volume startup failures.4,845,501 native stereo samples; peak7449,
 max adjacent step4361, no clipping. This is not a pop-free hearing claim.
- 3,668 stable busy-inclusive loop intervals are2frames:598school,1,746alley,
 477mall,847park. This is not matched original-NES speed proof.
- Exact health/dialogue controls preserve playfield pixels, sprite source and
 staging, counters, cameras and inputs. Health is still5frames (target3 FAIL);
 dialogue2–3frames. Full cross-ROM audio/register/RAM differences are retained.
- 1,389 unit tests pass in13.415seconds, including exhaustive empty-scan bounds
 and actual CHR-data/queue-liveness negative controls.

## Retained non-improvement and storage

3523 coalesces two empty eight-row scan groups. Its exhaustive bounds/ready-bit
tests pass and narrow playfield guards match, but health stays5frames. It is
not included in3527 and did not trigger a broad qualification campaign.

New large raw captures are under `/mnt/data/rcr-evidence-IT3Nti`, reached through
the project symlink `build/overflow-3526`. Existing artifacts were not moved or
deleted. Browser exports remain in `build/chr-starvation-published-3546` because
the evidence server correctly refuses symlinks that escape its root.

Still open: five-frame HUD publication, current menu/tile regressions, matched
original-speed workloads and physical/acoustic acceptance. The full goal is
not complete and3527 is not released.
