# Physical combat gaps: held-out music-context search

September18, 2026. Prior goal turn made progress by reconstructing the NES
reference filter and separating tails from packet/callback timing. This turn
investigates the three longer physical gaps in recording941. No ROM change,
restart, controller input or OBS mutation. Rival was accessed read-only to
inspect screenshot filenames/processes; its running game was not altered.

Review: <http://127.0.0.1:8766/triangle-game-physical-context-973/>.

## Findings

There are no135–165ms exact-zero gaps in the complete same-ROM emulator capture891.
Therefore, matching only the147–151ms hardware gap durations provides no useful
command correlation. A spectral context search instead finds repeated passages
of the same music. Offset selection uses physical seconds5–8, before the three
gaps; complete5–17s contexts must fit. The selected offsets are then frozen for
held-out10–13s and14–17s measurements. All eight separated candidates remain in
the report. No tempo stretch or per-gap alignment is allowed.

| Candidate reference offset | Training5–8 | Held out10–13 | Held out14–17 |
| --- | ---: | ---: | ---: |
| +45.950s | 0.915908 | 0.906819 | 0.883809 |
| +64.330s | 0.913786 | 0.905482 | 0.930313 |

These are cosine spectral scores, **not probabilities or waveform-fidelity
scores**. The training margin is only0.002122; repeated music prevents unique
game-event identification. Feature extraction resamples to16kHz, uses64ms
windows/5ms hops and80–5000Hz magnitudes with per-window normalization. This is
explicitly a location aid. Listening clips preserve the original PCM rates,
sample values and twelve-second durations; no audio normalization/resampling.

With the first fixed offset:

| Physical gap start | Hardware gap | Nearby reference gap | Start residual | End residual |
| --- | ---: | ---: | ---: | ---: |
| 9.099521s | 147.188ms | 114.482ms | −30.223ms | +2.482ms |
| 9.378833s | 151.438ms | 216.604ms | +66.536ms | +1.369ms |
| 13.491667s | 147.146ms | 216.542ms | +52.622ms | −16.774ms |

The second candidate retains a poor first-gap comparison (only31.305ms reference
silence), plus212.453ms and216.604ms later reference silences. These differences
are not discarded. Sound effects differ between the game encounters.

Actual received emulator packets command quiet throughout most of these
reference gaps. In the first candidate there are7,13,13 quiet packets followed
by an active packet0.343ms before the first nonzero sample. The unguarded
`all_reference_packets_command_quiet` field is correctly false: the onset packet
is preserved rather than hidden by a convenient boundary exclusion. The second
candidate has2,13,13 quiet packets followed by onset0.624/0.343/0.343ms before sound.
Every received packet and byte remains in report973.

This makes repeated musical rests with different decay/SFX context a plausible
explanation, but does **not** establish hardware command identity or resolve the
three physical gaps. The preserved differences are too large/ambiguous for that
claim. No slowdown, pop-free, full-game speed, or release pass is inferred.

## Screenshot disturbance check

The exact-frame collages show a MiSTer "Screen saved" overlay near the first two
gaps, with a10:09:59 timestamp. The third does not show it. Read-only inspection
found screenshots at10:08:59,10:09:59,10:10:59 and subsequent roughly60-second
intervals, including while paused. That does not explain three gaps within five
seconds and does not establish screenshot capture as a cause. No screenshot
service or setting was stopped or changed.

## Harness and next action

`locate_audio_context.py` and `audit_physical_audio_context.py` bind the physical
manifest958, normal capture891, actual packet timeline963 and unaltered audio.
Six tests locate an exact feature copy, retain repeated-match ambiguity, reject
silent/nonfinite/incompatible inputs, require full-context coverage, detect an
inserted missing signal and keep held-out offsets fixed. **696 tests pass**.

Preliminary searches970–972 selected each window independently and permitted
late training-only matches; their implementation binding is now historical.
Use973 for the constrained, held-out analysis. It explicitly leaves
`physical_commands_verified`, `physical_gaps_resolved`, `tempo_verified` and
`release_ready` false.

Next useful work is a controlled hardware sound cue with known input commands,
not more nearest-waveform matching. Also return to the original-speed/scrolling
regression matrix: these audio-location results do not discharge those gates.
