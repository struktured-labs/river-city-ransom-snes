# Isolated paired-byte SPC transport prototype

`prepare_audio.paired_engine` is an opt-in experimental function, never selected
by default game builds. It verifies the pinned engine, keeps the triangle fix, and
redirects the 15-byte receiver at $0487 to a 31-byte appended routine at
$3000. The original sound-processing entry remains $0496. The engine image
grows from $2C00 to $2C1F only in this diagnostic.

The CPU writes bytes to ports 1 and 2 before announcing the even index on
port 0. SPC stores both before acknowledging that index. Byte 22 is a
single-byte tail. The receiver returns with X=23, matching the old loop.
`AUDIO_PAIR` enables the matching sender and size assertion in bringup.
`check_audio.check(..., paired=True)` runs it in a fresh Python process.
Old-token-order, delay and eligibility-gate combinations
are rejected until their paired implementations have been tested.

Initial evidence:

- `build/paired-pulse-01` passes pulse, mute, restart and pitch signal gates.
- `build/paired-pulse-observed-01` matches its full WAV and timeline exactly.
- Actual SPC stores match all 7843 sent bytes / 341 packets, including the
  odd tail. Report `build/paired-pulse-receiver-audit-01.json`.
- The observer recognizes F5/F6 receive stores; the paired oracle requires
  PC $3008 for even indices and $3011 for odd ones. CPU bus observation also
  recognizes packet LDA $0A00,Y / STA $2142 (not IPL entry-address writes).
- Paired ACK validation checks upload marker Y=$2C21 and ordered even
  acknowledgements 0..22. Its ordinary-active-line latency filter qualifies
  only one packet (14650 clocks) and excludes 340. This is **not** sufficient
  evidence of a general latency improvement against the old protocol.

Executed follow-up evidence:

- `build/paired-transfer-controls-01/index.html`: correct receiver stores all
  7843 bytes without mismatch; changing its second-port read from F6 to F5
  causes 963 mismatches. Observer and normal-core PCM are byte-identical.
- `build/paired-retrigger-02`: periodic same-note retrigger profile passes
  the existing tone, silence, pitch and near-zero-run signal gates.
- `build/paired-sweep-reload-02`: controlled sweep reload passes; its
  missing-reload control retains the paired protocol and fails specifically
  with stale pitch in phase 3, as required.
- `build/paired-triangle-02/index.html`: stereo triangle, mute, restart and
  pitch pass. Its executed negative control also retains the paired receiver
  and restores only the original triangle-volume defect (SPC image offset
  $028E), reproducing missing right-channel sound. A unit test checks that
  this is the only byte difference between the two engine images.
- All 136 Python tests pass after these harness changes.

These are isolated signal checks, not a NES mix comparison, a frame-sequencer
validation, or evidence that gameplay popping has been eliminated. Controls
must use the same protocol as their positive case; the sweep and triangle
recursive checks now propagate that choice.

Matched full-scanline timing is now recorded in
`ABSOLUTE-SPC-TRANSFER-TIMING.md`: all 341 packets measured, about 14% shorter
data phase, observer audio/timeline equivalence verified. This is not a game
speed or audio-fidelity verdict.

Still needed: broader register patterns and waveforms, timer/
DSP continuity checks, then any game integration. Unit tests for malformed
streams do not replace these executed controls. The first opt-in game build
is documented in `PAIRED-GAME-VALIDATION.md`; no Rival deployment uses it.
