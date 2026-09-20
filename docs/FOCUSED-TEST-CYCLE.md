# Focused iteration before broad qualification

The sprite regression now has a single-command cycle:

```sh
python -m tools.run_sprite_cycle --candidate build/sprite-copy-game-3252 --out build/CHOOSE-A-FRESH-CYCLE
```

This verifies and reuses the source-bound parent capture, boots a fresh candidate
twice (observer off/on), checks the specific symptom, and produces a browser
collage plus JSON. It stops after 2,099 frames instead of the 9,248-frame route.
The measured individual observed replay took about eight seconds on blackmage;
the complete command also includes normal capture and evidence verification.
Each invocation records its own wall times. Existing trial pairs can be supplied
with `--trial-normal` and `--trial-observed`; those runs are explicitly marked
as reused, not timed as fresh emulation.

The narrow gate requires identical source generations and their production
frames, next-frame display of **every** known generation, unchanged original
game-counter/camera trajectories and delivered inputs, and no adapter faults.
It rejects dropped generations and three-frame delays, even if DMA is correct.
The first source generation remains explicitly left-censored.

The prefix is an explicit wrapper over the original scenario, not a silently
shortened full-route result. Every parent cache use revalidates source/core/ROM,
images, PCM, input policy, and same-core observer neutrality. Changed bindings
fail closed. No save-state restoration or emulated RAM edits are used.

Workflow:

1. Pin one observed failure and a small replay; write the symptom gate.
2. Change one mechanism. Run that cycle, inspect its collage, and retain failures.
3. Only after a visible/measured improvement, run the longer route, actual renderer
   and DMA checks, relevant menus, combat, and audio checks for that exact ROM.
4. Hardware presentation still requires the user's speed/audio acceptance;
   a focused PASS is not promotion, NES equivalence, or a pop-free claim.

Current experiment: convert sprites immediately after translated NES OAM copy
using the existing incremental converter, while leaving background, CHR, palette
and audio code alone. Initialization and hidden transitions keep the old producer.
The first fixed window improved from four three-frame delays plus five unrendered
generations to all 20 known generations displayed on the next frame. Broader
qualification remains separate.

## Exact-state row publication probes

The row-publication investigation now has authenticated32-frame health and
50-frame dialogue replays. Saving checkpoints5980/8232 on audio3408 preserved
the full9,248-frame timeline and native PCM (`build/row-checkpoints-3448`).
Fresh-process controls3449/3451 reproduced every original video frame,
game-RAM sample, PC/P/DB, delivered input and native PCM callback exactly.
Cross-ROM wrappers also demand identical initial full WRAM, VRAM and all eight
exposed CPU registers, and permit only a byte-guarded patch composition.

Example (existing outputs must never be overwritten):

```sh
python -m tools.half_row_scan replay \
  --core .deps/snes9x-voice-2292/libretro/rcr_voice_edge_libretro.so \
  --candidate build/guarded-volume-game-3408 \
  --normal build/guarded-volume-full-normal-3417 \
  --checkpoint-report build/row-checkpoints-3448/checkpoint-report.json \
  --frame 8232 --frames 32 --out build/CHOOSE-FRESH-ROW-PROBE \
  --trial build/half-row-scan-game-3458 \
  --resume-control build/row-resume-control-3449
```

Use5980/50 and `row-resume-dialogue-control-3451` for dialogue. Measured5.3–6.0s
per probe includes revalidating the full original capture. Reuse is explicit;
do not reuse these states across a changed core, parent, wrapper or input policy.
Historical instruction/DSP trace counters remain forbidden on restored runs.
Native PCM differences across cartridges are retained, never aligned away.

[Exact comparison3465](http://127.0.0.1:8766/exact-row-scan-review-3465/) retains
every RAM/image/audio field difference. Narrow playfield equality is a tradeoff
check, not masked full-picture equivalence. Two actual failing variants test
the gates:128-entry scanning delays sprites; per-block beam checking delays
dialogue. [Follow-up3474](http://127.0.0.1:8766/row-scan-followup-3474/) records
broader rejections:64-entry scanning still has two late sprite generations,
and the sprite-first candidate fails fresh boot. Neither is promoted. Short
restored passes cannot replace boot, transition or actual-renderer qualification.

## Check that queued graphics actually arrive

Completed-transfer safety is not queue liveness. Candidate3502 passed its DMA
and scanline audits while two CHR jobs remained pending for3,513 visible frames.
The early-OAM reorder had moved the CHR check past its old admission cutoff.
Candidate3527 restores admission and a new regression chain verifies the actual
original graphics bytes in VRAM, not just cleared job flags.

`tools/capture_chr_publication_state.py` runs the first-room boot prefix with
raw WRAM/VRAM snapshots across2390–2450. Its same-core observer/control must
preserve every primary video/input/state field and native PCM callback output.
The existing authenticated control can be reused; fresh observation takes about
6.7seconds. `tools/chr_publication_audit.py` retains all job generations and
censoring, rejects false retirement with stale VRAM, and checks every visible
pending span in the full route. See docs/EARLY-OAM-CHR-PUBLICATION.md and the
[current audit](http://127.0.0.1:8766/chr-starvation-published-3546/).

With the workspace disk nearly full, new large captures can use the already
created `build/overflow-3526` data-volume directory. Never delete user captures
or weaken the evidence server's root restrictions. Publish only selected
reviewed artifacts and byte-identical native WAV into a fresh in-root report.

## Authenticate machine-code continuation targets

A helper's abstract queue behavior can pass exhaustive tests while its jump
target points inside an instruction operand. Experiments3559/3569/3573 did this
at83D9; the actual scalar load starts at83D7. Neutral game instruction tracing
exposed the error. Preserve those failed replays, including censored text and
failed boots, rather than treating their apparent latency gains as optimization.

Execute emitted helper bytes against the independent queue oracle **and** verify
their entry/continuation opcode bytes against the exact cartridge. The real bad
helper must fail the latter gate. Then repeat exact-state health/dialogue and
ordinary boot before long campaigns.3583 combines fast empty-group reduction
with direct first-ready-word location; see `docs/MIXED-ROW-CONSUMER.md`.

## Partial sprite uploads require complete hardware-memory checks

For3955, checking only the256 uploaded bytes would miss a stale unused-slot or
high-table tail. `audit_oam_route_tail.py` compares all544 physical OAM bytes
after every upload and checks the static tail at renderer entry. Poisoned-OAM
fixtures exercise initialization, hidden transitions and changing live bytes;
real ROM and trace mutations must fail.

R-only events cannot explain forced-black lines. Core3984 logs the exact black
fill branch separately, and `audit_oam_blank_idempotent.py` accounts for every
line without assuming absent lines were blank. Duplicate identical B→B fills
are retained as idempotent; duplicate/mixed sprite rendering, absent spans and
wrong blank flags fail. Keep the earlier strict failed reports, not rewritten
green results. Verify full primary timeline/native PCM neutrality against the
same core; cross-core compatibility is a separate check.

[Full route3989](http://127.0.0.1:8766/early-oam-live-half-blank-review-3989/) covers
8,638 uploads and9,090 frames. It is not a live-sprite latency, all-scene or
acoustic certificate. Fresh observer replay26.447s plus5.586s verification;
reuse that result only with its exact cartridge/core/source bindings.
