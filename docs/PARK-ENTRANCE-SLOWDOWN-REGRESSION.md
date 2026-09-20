# Park entrance · physical slowdown regression

The live Rivalmage game on ROM `a501f707d4341e2ebaa1ce392a2a3cb327fd87a2703df06e0dee2d5d4f413f49`
was recorded by Blackmage's OBS/DeckLink scene on September 16. The owner
noticed occasional visual and musical slowdown while running among goons by
the U.S. Mail sign. The source is the *already running* OBS recording
`20260916_200806_struktured_v6c_part2.mkv`; no MiSTer reset, controller input,
OBS recording stop, or replay-buffer save was needed for this audit.

The [auditable park footage, stills, and pass/fail timeline](../build/park-slowdown-audit-149/index.html)
is linked to [machine-readable evidence and SHA-256s](../build/park-slowdown-audit-149/report.json).
The 120-second crop corresponds to seconds 2820..2940 of the OBS recording;
the park encounter is seconds 2885..2932. The saved video crop is lossless
after decoding OBS H.264, at game-scene resolution 256×144; a second aligned
video crop watches the original bottom-screen pause labels. Audio is 16 kHz
mono PCM from the recorded DeckLink audio track. The playable MP4 instead
retains the whole OBS frame and stereo/audible context from 2904..2916.

Observed review candidate: at recording time **2907.933 s**, during an active encounter,
the game-scene image is unchanged for **nine consecutive 60 Hz output frames**
(150 ms). Other game-scene pixels move in the half-second before and after;
there are no BELONGINGS/PASSWORD pause labels in that interval. Audio is
non-silent (median 469.5 PCM RMS). This establishes a repeated scene image,
not a stopped game tick, audio tempo drift, or full audio dropout. Subsequent
execution capture found repeated scene images while NMIs continued advancing.
The original 8-frame image-hold review threshold **fails** on this candidate,
but must not be presented as an independently proven performance regression.

A later 1047-frame still image overlaps a deliberate pause: the two original
pause labels occupy 1007 of those frames. The remaining **40-frame unpaused
lead-in** before the pause labels first appear (2913.4..2914.067) is reported
and separately trips the pre-label hold threshold; without captured button
timing it cannot measure input-to-menu latency. Video cannot yet say whether
game logic stopped early or the menu draw was delayed. Most of the 16.46 s
audio silence is within that paused interval; music and visible motion resume
within 33 ms after the menu closes. The silence is not presented as a 16 s
unpaused game/audio failure. An independent >200 ms *unpaused* blackout gate
passes. Audible but mistimed music remains **unverified** by this measurement.

## Automated regression

`tools/audit_park_slowdown.py` requires all three aligned observations: RGB
game-scene crop, bottom original-menu crop, and DeckLink PCM. It rejects
missing/misaligned channels and non-park scenes. It counts changed scene pixels
using a 40-level RGB threshold and a 32-pixel floor, so ordinary H.264 jitter
does not satisfy a motion gate. A failed run of eight or more output frames is
only the targeted **visual** gate; `tests/test_park_slowdown.py` has injected
nine-frame freezes, 260 ms unpaused silence and 20-frame pre-menu freezes,
plus an intentional pause that must not fail. A different encounter without
a pause is valid: only the known OBS reference uses `--require-pause`.

Repeat the checker with the hash-pinned local crop files:

```sh
python3 tools/audit_park_slowdown.py \
  --clip build/branding-ident-glide-audit-144/park-obs-2820-2940.mkv \
  --wav build/branding-ident-glide-audit-144/park-audio.wav \
  --menu build/branding-ident-glide-audit-144/park-menu-2820-2940.mkv \
  --source-offset 2820 --park-start 65 --park-end 112 --require-pause \
  --review build/park-slowdown-audit-147/review.mp4 \
  --stills build/park-slowdown-audit-145/full-2913.png \
    build/park-slowdown-audit-145/full-2917.png \
    build/park-slowdown-audit-145/full-2932.png \
  --out build/park-slowdown-audit-new
python3 -m unittest tests.test_park_slowdown
```

The first command exits nonzero **after writing its complete audit page**
because this real hardware clip contains flagged review candidates. It is not a tool
crash or missing evidence. The original 120 s FFV1 crops are ignored build
artifacts, not redistributable game art. To repeat on another session, use
`ffmpeg -ss <recording-start> -i <OBS-MKV> -t <duration>` with game crop
`crop=1280:720:340:145,scale=256:144:flags=neighbor`, bottom UI crop
`crop=1280:200:340:865,scale=256:40:flags=neighbor`, both video encoders
`-fps_mode passthrough -c:v ffv1`, plus `-map 0:a:0 -ac 1 -ar 16000` for
16-bit WAV. Preserve the same start and duration in all three extractions;
do not re-time, interpolate or skip video frames. The checker records their
hashes, verifies 60 Hz continuity and detects the original pause text.

## Input-only execution regression

The [execution timing report and NES/SNES screenshots](../build/park-execution-audit-154/index.html)
retain the failing deadline gate and all source hashes. The fresh receipt-bound
capture (`park-stress-snes-154`) also matches both earlier SNES runs byte-for-byte
for the complete timeline and PCM.

`traversal-park-stress` extends the proven shop-exit input route with eight
right/left double-tap run cycles and two pause/resume cycles. Original NES and
SNES captures complete approximately 9,400 frames each. They reach room 3 but
enemy/camera state diverges; this is not a forced identical-combat-state oracle.

`tools/audit_park_execution.py` verifies the capture receipts, delivered inputs,
matching scenario, and the ACK trace hash recorded by the same capture process.
It requires absolute-clock ACK timing; legacy eight-column logs are rejected.
The report separates static animation from interrupt progress, and excludes
pause, room changes, native transitions and non-gameplay tasks from the stable
park packet-deadline gate. The gate flags completion intervals over 1.5 nominal
NTSC frames; it does not certify DSP playback, musical tempo or acoustic pops.

On parent ROM `67010b850f65e0d64732fc8e8c238e33c071ed6c6337531a4814eb5bdcccabdc`,
the first absolute-clock run finds **41 stable-park delivery intervals above
1.5 frames**, longest **621,860 master clocks / 1.7401 frames**, during
`park_02_right_run`. Both boundary observations and the trailing video frame
are unpaused room 3, gameplay task, transition state zero. Longer room-transition
gaps remain visible in the report but do not count against this gate.

The restored observer was checked with isolated single/paired transport:
all 341 data phases per protocol measured, and ROM/WAV/timeline matched stock.
The complete park replay also has byte-identical WAV and execution timeline
between the current default core (`park-stress-snes-150`) and rebuilt absolute
observer (`park-stress-snes-152`). The observational change did not introduce
these gaps. See [observer restoration audit](../build/transfer-timing-restored-152/index.html).

CPU sampling near the early gaps repeatedly lands inside sprite conversion
with native NMI depth 1, followed by an unchanged NMI count on the next output
frame. This points toward masked producer work spilling past an interrupt
deadline, but opcode counts alone do not establish the complete cycle budget.
The next optimization must preserve OAM/CHR/row output and demonstrate improved
packet deadlines; eliminating a still-image warning alone is not sufficient.

Reproduce the audit from the retained observations (expected exit status 1
while the measured deadline regression remains):

```sh
python3 tools/audit_park_execution.py \
  --reference build/park-stress-nes-150 \
  --candidate build/park-stress-snes-154 \
  --ack build/park-stress-snes-154-ack.csv --engine-size 0x2c7f \
  --out build/park-execution-audit-new
python3 -m unittest tests.test_park_execution tests.test_park_slowdown
```

Nine execution-auditor unit tests cover final-frame hold flushing, input-phase
boundaries, advancing interrupts on identical animation frames, counter wrap,
pause/transition exclusion, legacy timing rejection and substituted ACK traces.

The subsequent [incremental sprite experiment](SPRITE-DELTA-EXPERIMENT.md)
reduces the number of observed late packets but still fails the deadline gate
and whole-route checks. It remains opt-in and has not been deployed to Rival.
