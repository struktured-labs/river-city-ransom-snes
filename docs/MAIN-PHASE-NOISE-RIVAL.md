# Timing and noise correction: current Rival test build

Rival was restarted at **2026-09-17 18:57:58 UTC** with branded799:
`840de24fb8e17e8ffb48b08a16ce60831081ef221e4e69a25eaf6f39b053bae5`.
The initial deployment was left at the **1P selection menu**, without injected
input. A later bounded hardware combat test left it **paused by Trash Pick-Up**
in room1, with runtime **SNAC restored to Yes** and OSD closed (see below).
The previous616 ROM/launcher remain available. No saved controller configuration,
OBS scene, recording, replay, gain or mute setting was changed.

This is a qualified test handoff, not release completion. The standing restart
authorization was used after a stronger park-speed benchmark: all1,003 observed
stable gameplay iterations consumed exactly two native interrupts and all1,002
consecutive iteration starts were two frames apart, matching the original
two-tick main-loop contract. Different encounters still prevent an equal-work,
full-game or input-latency certification. The strict background-publication
gate remains open; it was not removed to permit this test handoff.

## What changed

The line128 scheduling candidate783 is combined with the previously qualified
noise-clock correction. Relative to783, the exact ROM reconstruction permits
only ten SPC lookup-table bytes and two checksum bytes. No instructions,
artwork, splash ident,240-frame logo hold or controller mapping changed.
Controller presets remain disabled; this is not a new bass-ident design.

Full-route normal captures preserve all9,403 non-audio frames byte-for-byte,
including video hashes, original game RAM, native telemetry, inputs and audio
callback sample boundaries. All non-noise sound is sample-identical. Independent
SPC observers prove all8,950 packets and bus/key-on/synthesis/receive traces
identical between the two builds (`main-phase-noise-review-804`).

The same40,222 ordered APU writes were replayed through a banked NES stimulus,
with physical-write, missing-frame and bank-switch negative controls. Across
398 register-selected steady noise frames, mean spectral centroids move closer
to that reference at all three observed rates. The smallest group has only
three frames. This is spectral evidence, not complete APU fidelity or subjective
sound quality. Full-mix maximum sample step falls4,677→3,996; peak rises6,390→6,521.
No clipping or missing callbacks; unchanged transient thresholds pass. No claim
that all audible gameplay pops have been eliminated.

## Speed and rendering evidence

- `main-phase-full-loop-audit-811`: neutral host-only observations at the actual
  iteration start, input call and original `$F2DA` completion.1,003 stable park
  loops, every one exactly two NMI ticks; no over-two-tick loop. Boundaries and
  all excluded non-park iterations are retained.
- `main-phase-noise-nmi-808`:2,023 stable park interrupt intervals, none over
  the unchanged1.5-frame limit. Actual clock range356,466..358,260. An older
  missed-VBlank capture produces four late intervals and is rejected.
- `main-phase-noise-park-806`: no stable park SPC packet gap over1.5 frames.
- `main-phase-noise-renderer-808`: full neutral renderer replay;7,785 eligible
  frames completely covered, zero splits, zero extra-frame stale holds.
- `main-phase-noise-holds-809`: zero1/3/4-frame irregular holds east and west;
  entire displayed-camera distributions match783, including long stops.
- Candidate783's fixed-offset room fades, short movement, Present Status and repeated
  café menus pass. The table-only combination's whole-route rendering/state
  equality is separately proved; no new hardware shop playthrough is claimed.

## Expanded coverage and retained failures

New `traversal-expanded-sweep` adds bounded, ordinary-input alley return trips
and then continues through the café/park. Historical scenarios/policies are
unchanged. Both cores use the same preceding-state policy; no game memory,
savestate, death recovery or favorable-frame search is used. Imported policy
dependencies are now hash-bound and changed/missing dependencies are rejected.

Expanded captures796 compare211 alley positions instead of37, all exact.
Both background observers are timeline/PCM neutral. The full report797 remains
FAIL: the original NES run returned to the mall during its park-east attempt
and timed out, whereas SNES completed. Park common coverage is consequently1;
the failed original route was not relabeled successful. Across all582 common
positions, every selected background is exact and settling is no later.

Initial renderer803 used misspelled bound variables, retaining only7600..8420;
audit805 correctly failed coverage. `validate_render_options` now rejects those
unknown variables before capture. Replacement807 observes1..15000, and808 passes.
The old combined stage-cost auditor806 also rejects the new graphics call order
because its required adjacent edge8→7 no longer occurs. The independent NMI
auditor does not weaken that stage-cost requirement; it measures actual NMI
entries and rejects the real older missed-interrupt control.

The deployment qualification had625 passing Python tests. New tests cover route bounds,
input-only decisions, first completion/timeouts, dependency bindings, renderer
option mistakes, NMI gaps, loop overruns, counter wrap and incomplete events.

## Physical deployment and sound

`main-phase-rival-deployment-818.json` binds the local/remote ROM hash, launcher,
observed process arguments, screenshots, recorded media and audit reports.
Remote launcher is `/media/fat/RCR-SNES-840de24.mgl`; ROM is
`/media/fat/games/SNES/RCR-SNES-840de24.sfc`. Saved SNES.CFG stays
`066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
This proves file/process identity, not cartridge-RAM readback. Saved-file
identity does not independently prove runtime SNAC state or physical buttons.

Read-only extraction of the existing Blackmage recording spans61938..61968s.
The30-second stereo48kHz WAV is decoded PCM; the browser MP4 is re-encoded.
The first live screenshot813 was too early and shows a black load interval;
recording still816 at61946s shows the full logo, and live screenshot814 shows
the original1P menu. These frames are kept separately, not mislabeled.

Physical ident audit817 passes all12 pitch windows, silent reveal/cutoff and
game-music resumption (RMS374.97); maximum ident step327. This is real
MiSTer→Blackmagic→OBS sound, not emulator audio. It confirms the boot/audio
handoff, not physical gameplay speed or intermittent-pop elimination.

Review and current handoff: <http://127.0.0.1:8766/main-phase-rival-review-819/>.
## Physical gameplay follow-up

No further restart or ROM change. SNAC was temporarily disabled at runtime for
a bounded USB sequence:70 cycles of Right+Y+B for80ms, Right for420ms, then
release/Start/release. Input receipts have actual wall-clock times, not
frame-exact acceptance. Before/after saved SNES.CFG hashes match. Screenshot832
shows runtime SNAC **Yes** after restoration;833 shows OSD closed and game
paused. A screenshot-saved overlay appeared at pause, likely a USB hotkey side
effect; that file was not deleted. No physical SNAC-button verification claimed.

`main-phase-gameplay-835` binds30 seconds of physical combat at recording
62565..62595 and20 seconds paused at62605..62625. Both are stereo48kHz PCM16.
The gameplay video was re-encoded from the same requested window; ffprobe
reports30 seconds/1,800 frames. Gameplay AC RMS is494.37/494.38, peak2,624,
largest adjacent sample step1,134, zero clipped samples. Every one-second
interval contains audio. The paused interval is **exactly zero** in both
channels. Silent-gameplay and one-sample-paused-click negative controls fail
the narrow pair gate as intended. This is not a pop-free or speed certificate.

`main-phase-physical-transients-837` adds eight strongest separated sample-step
clips and all four exact-zero spans at least10ms long, retaining amplitude and
exact sample/recording offsets. The longest silence is114ms at62579.495375s;
video stills show street→black transition→Trash Pick-Up around that interval.
The other spans are13ms,13.125ms and25.792ms; their musical/driver cause is not
established. All remain in the report, not excluded from metrics. Sensitivity
tests detect inserted full-scale discontinuity, clipping and50ms silence.
These are review candidates, not automatically classified audible defects.

The pause-pair HTML now takes ROM identity and recording offsets from the
manifest instead of hardcoded historical values and requires bound review
media. End-to-end tests protect those labels, media bindings and exact PCM
slices in the new transient review.

After these harness changes,633 Python tests and `git diff --check` pass.

## Longer endurance attempt

`main-phase-endurance-normal-828` executes11,323 frames and remains **incomplete**.
Its first9,403 timeline rows equal the passing single-lap800 capture exactly.
On the second eastward pass, frame10030 visibly says “ALEX has lost all of his
power.” Room changes3→2 at10072; frame10150 shows the Grotto Mall respawn.
The policy requires park room3, so it releases input outside the room and
eventually hits its1,920-frame waypoint timeout. This explains that route
failure, not combat equivalence or full-game performance. No death recovery,
RAM mutation, timeout relaxation or successful-endurance claim was added.

Next: correlate the shorter physical audio gaps with sound-driver events,
sustained surviving park coverage, input-to-render latency and broader scenes,
retaining the still-open strict and acoustic checks.

Later [physical park follow-up](PHYSICAL-PARK-REVIEW.md) reaches the park and
records a surviving sweep plus a separate death/respawn pass. Scenery timing
retains two four-frame intervals and ten ambiguous pairs. SNAC restored Yes;
same ROM, game paused by Trash Pick-Up.646 tests now pass. No pop-free or
full-game speed certification.
