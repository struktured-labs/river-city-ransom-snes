# Sprite-coordinate arithmetic: faster, still not a qualifying release

Candidate694 (`38d9b7a3c39f6d9407ed70e1a8b03a5cf4b8692c06a60efa58087cbc0b0eeca2`)
adds default-off `--experimental-sprite-coordinates`. No Rival restart,
hardware input, OBS change, sound-engine replacement or original-art change.

## Actual source of work and implementation

The parent608 instruction trace650 shows original `$EF11..EF25` repeatedly
adding two sprite coordinate/offset pairs through an indexed two-iteration
loop. The replacement performs the same byte additions without loop/index
bookkeeping. It deliberately retains8-bit ADC, including decimal-mode behavior
on the SNES CPU. Final A/B/X/Y, carry/overflow/negative/zero, DP/DB/stack and
source offsets are preserved; no game timer or interrupt policy changes.

The initial682 version inserted the helper ahead of existing runtime code.
Candidate694 instead appends33 bytes in unused padding. The scoped verifier
696 proves all68 existing nonlocal runtime labels remain fixed and only295
cartridge bytes differ: eight helper copies, nine mirrored entry jumps and
checksum. The ninth jump is the selected last PRG pair's `$C8:AF11` mirror.
The helper bytes equal the executed oracle's helper. Disabled694 is byte-for-
byte parent608. This avoids attributing unrelated code relocation to the
arithmetic optimization.

## Executed correctness and timing

`sprite-coordinate-oracle-690` executes the original pinned loop and replacement
for all65,536 low-byte input pairs—131,072 routine executions—with varied high
bytes, flags, hidden accumulator byte and input registers across eight banks.
All32-byte result records agree. The32,768 binary-mode cases also match an
independent arithmetic/register oracle. All unrelated zero-page bytes and
source offsets are checked. Six actual mutants fail: missing carry clear,
wrong high operand, wrong exit flags, changed Y, missing high store and changed
decimal mode. No interrupt was injected in this fixture; decimal comparisons
are original-loop SNES behavior, not a claim that NES decimal arithmetic exists.

Early fixture attempts failed on an incorrect DB mirror, insufficient execution
time and mutation includes resolving to the original source. They remain
retained and are not passes. The final fixture compiles beside each arm's
helper, so mutations actually enter the executed cartridge. Mutation survival
prevented either incomplete run686/688 from producing a passing report.

`sprite-coordinate-timing-691` observes actual `$EF11` entry through `$EF26`
continuation for8192 matched cases in four matrix chunks. It includes the new
jumps and DRAM/event time. Each timing run's whole WRAM matches its own normal
execution. Mean elapsed clocks are463.6328→333.6875, saving129.9453 (about28%).
Every matched case is faster; minimum saving86 clocks. **This is the small
coordinate loop, not28% faster gameplay.**

## Full game checks and reasons not to deploy

The exact694 normal, renderer, background and stage/ACK captures all complete
8696 frames. Observers match their normal full timeline and PCM. Different
encounters prevent interpreting total route duration as a speed ratio.

| Uniform2px 1/3-frame camera pairs | NES | Parent608 | Preserved-layout694 |
| --- | ---: | ---: | ---: |
|Park east|3|11|17|
|Park west|0|18|8|

The return improves, outward travel does not. Earlier relocated682 measures
16/9 pairs; adding the tested line30 cutoff to that version692 measures18/13,
so that combination does not establish a fix either. Complete histograms,
long stops and censored edges remain in `sprite-coordinates-display-696`.

- Background:818 selected positions are exact (259/118/99/342 across four
  rooms), but publication/settling gates still FAIL. Audit698 retains them.
- Renderer:7381 complete eligible frames have no split;6422 covered
  unchanged-camera checks have no stale hold. Missing all160 renderer lines
  at first-room fade frame2117 remains a coverage failure, not a skipped pass.
- Whole loads:21/29/29 frames versus NES20/31/30. The first load regresses
  one frame versus parent608; fixed-offset fade comparison also fails.
- Present Status: first opening/reopening have zero mismatching pixels.
- Short movement:21px on both systems, all checked target arrivals no later;
  not a combat-speed proof.
- Stable park NMI timing: zero long intervals in exact-candidate report698.
  CPU ACK audit699 validates8548 packets. This does not certify acoustic
  fidelity or eliminate the user's intermittent pops. No audio fix claimed.

553 Python tests pass. Source/artifact hashes for the final arithmetic oracle,
timing observation and cartridge-scope proof are revalidated. The faster helper
is retained as an experimental option; it is not a full-speed/scrolling pass.
Next work must address the camera publication deadline and first-fade timing
without hiding a frame of latency or changing original game ticks.

Review: <http://127.0.0.1:8766/sprite-coordinates-review-699/>.
