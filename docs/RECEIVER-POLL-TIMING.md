# Faster SPC polling and room-load timing

September 18, 2026. No Rival deployment or restart during this investigation.
At the end of that investigation, hardware remained `fa882cb61138`.
The subsequent [Rival deployment and physical trial](RECEIVER-POLL-RIVAL.md)
now document the combined build on hardware. Graphics, controller presets and splash
art/sound are unchanged by the receiver experiment.

## Cause narrowed with actual game instructions

[Mall scheduling and nested sound-call costs](http://127.0.0.1:8766/mall-fade-timing-1429/)
compares fresh, complete neutral captures of NES, older build783, current1321,
and cutoff128. First four main-start → fade-service frame offsets:

| Build | First | Second | Third | Fourth |
| --- | --- | --- | --- | --- |
| NES | 1→2 | 3→4 | 5→6 | 7→8 |
| Older783 | 1→3 | 3→4 | 5→6 | 7→8 |
| Current1321 | 1→3 | 3→5 | 5→6 | 7→8 |
| Cutoff128 | 1→2 | 3→3 | 5→5 | 7→7 |

The cutoff trial restores the initial service but later runs the original
fade logic early, consistent with its early mall colors. A service call is
not itself palette generation or display. No room-specific delay was added.

The initial SPC-ready wait takes only112–152 master clocks in both old and
current mall windows. The sender already returns after last-byte receipt,
without waiting for synthesis to finish. This rules out removing a supposed
final-ready wait as the fix. Actual paired-byte waits dominate instead:

| Ten mall publications | Older783 | Current1321 | Receiver trial1430 |
| --- | ---: | ---: | ---: |
| Mean complete audio bridge, master clocks |16,009.2|29,360.0|25,440.4|
| Mean nested wait routines |10,923.8|24,265.0|20,369.8|
| Mean bridge work outside sender |849.2|852.6|856.6|

Do not add these overlapping measurements. Wait routines include checks and
returns, not exclusively CPU stalls. Builds have different game timing;
these are measured windows, not identical-packet latency pairs or a global
speed ratio. NES CPU cycles and SNES master clocks are different units.

## Implemented default-off receiver fast path

`tools/build_receiver_poll_trial.py` patches20 cartridge bytes, all inside
the SPC image and SNES checksum. The old receiver wait calls a clock routine
even when Timer0 is empty. The replacement reads/consumes Timer0 once, returns
to reception quickly for zero, and calls the unchanged pending-tick body for
nonzero. It preserves active-control swapping, X/Y saves, clock residual,
receiver store PCs, publication, KON ordering, samples and upload length.
Exact opcode/target/padding preimages are mandatory.

The first build attempt correctly failed closed: the generator expands the
conditional into BNE/JMP, not a literal BEQ. The builder now verifies that
actual seven-byte prologue before selecting the pending-tick entry. No invalid
cartridge was emitted. Failed capture directory1431 is not a completed run.

Executed checker1433 tests both real engines, both four/five-step modes and
sender delays0/256/512/2048. Each of sixteen cases boots, sends101 packets,
including100 without a clock reset, then idles one second. Continuous
half-frame deadlines pass while packets are stalled. A damaged helper that
discards consumed timer deltas is detected. No-delay fixture packet times are
unchanged; this test does not claim every transfer is faster.

Fresh complete game audit1437 checks8,353 received packets, no bus leftovers,
ready coverage, unchanged expected reset/duty events, correct configuration
before restart, and exact raw-DAC/delivered-PCM identity. Both instruction and
DSP observers preserve the complete8,809-frame normal replay. All packet
contents are checked at actual receiver instructions, not inferred from sound.

[Receiver-only profile and unshifted failure collage](http://127.0.0.1:8766/receiver-poll-game-review-1437/).
All eleven web artifacts were fetched and hash-checked. Receiver-only first
visibility is8/7/7; room-change-to-visible20/28/29 and rendering-off-to-visible
21/29/29. Alley offsets7/11/15/19 remain wrong. It is not a qualified release.

## Combined row-conversion result

Candidate1438 combines the receiver fast path with the already executed compact
hidden-row converter, with no budget/deadline/fade-counter change:
`339d2b220a3a921626980f1e197ef4a606e16103093824f95f5649004bf00b74`.
Normal1439 completes9,406 frames; route duration is not an equal-work benchmark.
Patch audit1441 reassembles both variants, verifies the disabled parent exactly,
and binds the new helper to the actual6,144-case VRAM oracle1389. Only720 bytes
inside the helper/checksum differ from receiver-only1430; outside boot/runtime
symbols remain unchanged.

[Combined build's full room-entry comparison](http://127.0.0.1:8766/receiver-poll-index-entry-1440/):

| Latency, rooms1/2/3 | NES | Combined1438 |
| --- | --- | --- |
| Rendering enable to first scenery |7 /7 /7|7 /7 /7|
| Room change to first scenery |20 /31 /30|19 /28 /29|
| Rendering off to first scenery |20 /31 /30|20 /29 /29|

All forty fixed-offset backgrounds in every room match, and every existing
entry gate passes without changed thresholds or frame alignment. This is a
real loading improvement, not a full-game original-speed or audio-fidelity pass.

## Fresh combined-build qualification

Main1442, DSP1443 and renderer1444 are fresh complete9,406-frame captures;
their full timelines and PCM match combined normal1439. No receiver-only
timing/audio/renderer result is inherited.

- Cadence1445 passes3,823 stable main iterations across four rooms, all two
  NMI ticks, with every qualified consecutive start two frames apart. Both
  park directions have zero short irregular camera holds;14-frame stops are
  retained. A three-tick mutation is detected.
- Renderer1446 has zero incomplete coverage, split-scroll or stale-held-camera
  failures across all eligible frames. This does not certify tile content or
  all physical display behavior.
- Audio1447 passes actual packet/DAC/ready checks and1,638 restart orderings,
  with zero late configuration writes. A deliberately late write is rejected.
  This is protocol/order qualification, not a DSP-latch or acoustic-pop verdict.
- All fifty artifacts in entry review1440 were fetched over HTTP and hashed.

The independent pitch-prefetch audio trial is **not** included (its experimental
padding overlaps this helper). Physical pops, original-waveform fidelity and
broader speed/scrolling requirements remain open.874 unit tests pass, including
wrong-token/missing-wait/stack and opcode-preimage controls. Next is a bounded
physical trial of this exact cartridge with real capture audio and retained
controller settings; no hardware result is claimed in this report.
