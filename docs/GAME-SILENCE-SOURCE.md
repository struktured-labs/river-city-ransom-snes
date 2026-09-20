# Distinguishing musical rests from missing game audio

Follow-up: [triangle boundary experiment](TRIANGLE-BOUNDARY-EXPERIMENT.md)
tests concrete note-off/on changes with phase-varied executed SPC/NES probes.
It remains opt-in and unqualified for deployment; no silence gate was relaxed.

Rival remains on `840de24`; this investigation does not change the ROM or
restart the game. The previous physical recording contains three13–26ms gaps
and one114ms street-transition gap. Those physical events are not frame-matched
to the emulator scenario and are not declared resolved by the analysis below.

## Same ordered writes on both engines

`main-phase-full-nes-stimulus-841` executes all40,222 captured CPU APU writes
through the NES core, retaining their order and scheduling them at actual SPC
packet-publication frames.9,403 source frames and five bank crossings complete.
Physical-write suppression, omitted empty-frame guard and omitted bank switch
are independently rejected. This is a full mix, unlike the earlier noise-only
stimulus802. Intra-frame write timing remains frame-quantized, not cycle exact.

The original802 prerequisite correctly rejected reuse after a harness-source
change. Fresh provenance840 revalidates all8,950 packets, actual received bytes,
key-on schedule, processing completion and full normal/observer neutrality.
No hash was edited to bypass that failure.

`main-phase-same-write-rests-842` exposes source frames1260..1500 as unnormalized
NES/SNES WAVs with per-frame metrics and shared-full-scale waveforms. The
different overall gains are retained; absolute amplitudes are not treated as
fidelity equivalence. A representative triangle rest is:

| Source frame | Published triangle control | NES peak / largest step | SNES peak / largest step |
| --- | --- | --- | --- |
| 1283 | `$81` (linear count1) | 4,964 /728 | 2,287 /231 |
| 1284 | `$80` (linear count0) | 4,582 /545 | 1,762 /430 |
| 1285 | `$80` | 198 /1 | 0 /0 |
| 1286 | `$81` | 6,585 /1,490 | 2,314 /665 |

Both pulse volumes and noise volume are0 at the1284/1285 packets. The NES
recording's small smoothly changing tail is not sustained missing melody.
The inspected FCEUmm `RDoTriangle` source retains the current DAC level when
length/linear counters halt; the SPC output instead reaches digital zero.
Filter/phase behavior and attack transients still differ and remain fidelity
work, not grounds for claiming the entire sound emulator is accurate.

## New fail-sensitive held-voice check

`analyze_game_silence.py` finds every exact-zero gap at least10ms long in the
full unmodified PCM. It checks actual published/received packet state, not the
CPU shadow: that shadow can contain a newly started note not yet sent to SPC,
or an enable bit masked by the checked length-eligibility adapter.

For an active-voice regression, the **same** enabled constant-volume, length-
halted voice must remain active from two source frames before the gap through
one after it. Pulse sweep/envelope ambiguity is not guessed. DMC is not modeled.
The counter/period guards and complete packet coverage are explicit; without
positive held-voice coverage the check cannot pass.

`main-phase-game-silence-843` finds4,868 qualifying held-voice frames and **zero
held-active-voice silent gaps**. All712 gaps inside packet coverage have an
explicit mute command in or immediately before their frame range. Because
their guarded windows also include note boundaries, they remain classified
`boundary_or_unresolved`, not promoted to proven intentional rests. Two gaps
are outside packet coverage. All714 remain in the report.

Independent injected full-callback silences in the actual menu, street-idle,
shop and park waveforms must each produce a new failure at that exact interval.
The actual packet commands are unchanged in those negative controls.639 unit
tests pass, including callback holes, packet order, retained packet state,
same-voice requirements, unknown envelopes/sweeps/DMC and no-coverage refusal.

This is a narrow dropout regression, not a click detector or physical audio
certification. Next useful work is onset/offset and filter behavior, plus a
longer surviving physical park capture. Broad gain changes, extending note
lengths or smoothing away real rests are not justified by these results.

Review: <http://127.0.0.1:8766/main-phase-audio-rest-review-844/>.
