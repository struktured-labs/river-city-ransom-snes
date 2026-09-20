# Direct-input PCM identifies downstream monitor sample loss

Review: <http://127.0.0.1:8766/common-pcm-review-1809/>

**Concrete result:** this instrumented hardware run has stable AAC/common-input
correspondence but missing samples in the downstream raw-monitor stream. We
can now use direct incoming PCM as the hardware audio reference, instead of
treating monitor timing changes as evidence of an SPC defect.

This is a harness improvement and capture-path diagnosis, **not** a ROM fix,
pop-free claim, or an explanation of every user-heard glitch. Rival remains on
`0e9ba29becef`, paused on the school street, SNAC Yes, OSD closed. No restart.

## Acquisition and qualification

`obs_common_pcm.bt` reads only DeckLink's interleaved submission to OBS and the
corresponding common float source callback. The probe is gated by the DeckLink
call stack/source identity. It does not capture desktop/microphone sources,
write process memory, or change OBS settings. The installed binaries must match
the established hashes. Instrumentation adds overhead; neutrality is unproven.

Payload capture uses the documented [bpftrace buffer reader and hex format](https://bpftrace.org/docs/release_023/stdlib).
The decoder rejects truncated payloads, skipped or duplicate sequences,
unpaired callbacks, changed source identity/format, mismatched timestamps,
nonfinite float data, trace warnings and missing boundaries. It never fills a
gap or conceals a missing packet by concatenation. Packet timestamps and frame
indices accompany the native WAVs.

Initial short observation `1786` had an arithmetic signedness warning. It is
retained, unqualified; the cast was corrected before the clean `1787` capture.
Clean paused decode `1788` contains 177 complete pairs and only zero samples;
that validates transport/format, not sound quality.

Gameplay `1795` / decode `1799` contains **2,398 complete pairs**, **1,918,403
stereo frames**, 2,052,792 nonzero channel samples. Native input is S16 stereo,
48 kHz. Every common float sample equals the corresponding native input sample
divided by 32768, exactly: zero differing samples over the entire observation.
The common trace brackets the controlled input interval on the same host's
monotonic clock. It remains downstream of MiSTer, HDMI and DeckLink.

## Independent branch comparisons

The original raw/AAC check still fails: held-out correlations at seconds
8/10/12/17/19 are 0.979513 / 0.787137 / 0.708542 / 0.642516 / 0.696904.
These scores remain in the report; they were not replaced with fitted passes.

Using the new common PCM reference, each branch receives its own early fixed
alignment. All one-second diagnostic windows from AAC time 4 through 22 remain:

- Common versus AAC: fixed offset 553540 samples; diagnostic delta **zero in
  every window**; fixed correlations 0.996364–0.999894.
- Common versus raw monitor: initial offset 283809; subsequent diagnostic
  delta 0 → 1 → 33 → 34. Between transition windows, local correspondence is
  essentially exact. Searches are diagnostic; native audio is never retimed.

The common/native equality and stable recording correspondence locate these
particular shifts **downstream in the monitor branch**, not in shared game
audio. This does not transfer retrospectively to earlier unobserved captures.

## Exact native comparison

With the actual OBS volume `0.4216965138912201`, float32 multiplication and
truncating S32 conversion, all **864,000 stereo frames** in the selected
18-second monitor interval match the common signal, apart from reference-only
blocks of **1, 32 and 1 frames** (34 total).

| Observed monitor frame | Common reference frame | Reference-only frames |
| ---: | ---: | ---: |
| 603648 | 887457 | 1 |
| 751616 | 1035426 | 32 |
| 1276416 | 1560258 | 1 |

The bounded matcher tests both directions up to 128 frames, requires one unique
candidate and 2,048 exact following stereo frames, and fails on ambiguous
candidates or insufficient tail context. It diagnoses sequence differences;
it does not repair audio. A boundary within repeated samples need not identify
the actual discard instant. We have not identified the downstream instruction
that caused the loss.

The remaining 13.895833 ms interior silence is already present in the common
input: frames 920841–921508 are zero, with nonzero neighbors. It is therefore
not manufactured by these downstream monitor deletions. Musical rest versus
synthesis/upstream fault remains open without same-run sound-command evidence.

## Review, checks and handoff

The web review retains full video, controller-state/paused screenshot collage,
every fixed and diagnostic score, the raw silence excerpt, and six unchanged
source/monitor excerpts around the three sequence discrepancies. Source and
monitor listening levels differ; clips are not gain-normalized.

- Native observer: `build/obs-common-game-pcm-1795/`.
- Input/capture coordination: `build/obs-common-game-1796/`.
- Native S16 and float WAVs plus complete packet index: `build/obs-common-game-decoded-1799/`.
- Audio/camera reports: `build/common-probe-audio-1803/`, `build/common-probe-camera-1807/`.
- Branch attribution: `build/common-pcm-branch-audit-1806/`.
- Exact sequence diagnosis: `build/monitor-pcm-edits-1808/`.
- Original recording: `/home/struktured/Videos/drmario_sessions/20260918_175155_struktured_v6c_part2.mkv`.
- Review `1809`: all **24 served artifacts** hash-verified; **seven native
  excerpts** sample-verified; encoded video/audio unchanged from original.
- Full suite **967 tests pass**, including 13 new payload, branch-localization
  and exact-sequence tests. Synthetic deleted samples in either branch are
  distinguished; corruption and ambiguous edits do not pass as known drops.

Camera evidence retains all 12 rejected adjacent pairs and one 1-frame hold;
the remaining equal-step holds are `{2:13,26:8}`. Not original-speed proof.
Recording stopped; raw debug tap removed; adapter links/properties, saved
SNES.CFG and OBS audio settings unchanged. SNAC restored in screenshot `1801`;
paused OSD-closed handoff `1805`.

Next use qualified direct-input PCM for physical SPC/command comparisons and
real audible-transient regression. Monitor recordings remain useful evidence,
but are not an unquestioned timing reference. Remaining sound quality, rare
slowdown and full-game scrolling requirements are still active.
