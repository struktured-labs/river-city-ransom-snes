# Three-port audio transport: verified faster, not promoted

Experimental candidate549:
`a00b86919c31df3d51e6d973564e981865fa1938c771de19a385f75b40f85eca`.
Only existing paired/triple options change from candidate539. No production
SPC/sender patch, default change or Rival restart. Candidate539 remains the
working comparison build. Original-speed, complete scrolling and audible
fidelity remain unmet.

## Measurements, not a whole-game speed claim

| Handshake ACK through final data ACK | Paired539 | Triple549 |
| --- | ---: | ---: |
| Complete measured packets |9,233|9,093|
| Minimum master clocks |13,432|9,632|
| Maximum master clocks |13,722|9,952|
| Mean master clocks |13,600.44|9,826.05|

Fresh reports `chr-low-park-audit-558` and `camera-triple-park-audit-555`.
The data-transfer phase is about27.8% shorter, saving about3,774 clocks
(2.77 ordinary scanlines) on average. Initial ready wait and synthesis are
excluded; different complete game runs are not packet-by-packet matched.
Neither run has a stable park packet interval above1.5frames.

Loading regresses: `camera-triple-entry-551` reports22/29/29 versus NES
20/31/30 and parent21/28/29; first-visible offsets8/7/7 versus7/7/7.
Do not promote a faster mailbox on this evidence.

Parent camera trace547/cost548 binds a late completion at7555,line39 to
15,082 clocks NMI-to-driver,13,286 driver-to-bank-restore,1,136 restore-to-
sender, and54,380 sender-to-camera. The last includes remaining main work,
not just sound. Triple camera trace553 remains late in multiple sampled
frames; its adaptive route is not identical game state at the same frame
number. No39-to-X improvement claim is made by shifting those samples.

## A real harness gap closed

The old CPU observer recorded only ports1/2, omitting every third byte.
The old receiver observer recognized only the paired store layout. The
strict triple run550 therefore fails the complete-byte parser; the paired
ACK parser also correctly rejects its tokens. Neither error was waived.

An isolated copy `.deps/snes9x-triple-552` adds port3 CPU observation and
`tools/snes9x_triple_receive.inc`: all24 actual SPC stores, including the
zero padding byte. Existing pinned cores/sources are untouched. The copy's
`cpuexec.cpp` accepts packet STA $2143 alongside $2142; its SMP core includes
the new observer instead of the paired fragment. Build with:

```
make -C .deps/snes9x-triple-552/libretro -j4 -W ../apu/bapu/smp/smp.cpp
```

The explicit dependency is important: the Makefile does not track changes
in `core.cpp`, which is included by `smp.cpp`. An initial incremental link
was followed by this forced SMP rebuild before any qualification captures.

`benchmark_capture.py` now flushes/binds receive-store logs contemporaneously.
The strict receiver validator requires indices0..23, exact pinned store PCs,
all23 data bytes and zero padding, with no omissions. ACK validation requires
tokens0,3,..21 and the sender's advanced Y3,6,..23. Packet/header/synthesis
validation requires triple PC300C, never paired3008. Relabeling one protocol
as the other fails. Triple provenance now **requires** a complete receive
trace; old four-field header checks alone are explicitly labeled as such.

`triple-protocol-oracle-558` runs the production sender/receiver diagnostic:
7,843 data bytes,8,184 physical stores, zero mismatches. Separate actual
wrong-port1/2 builds each produce613 mismatches; wrong-port3 fails the zero
padding invariant. All mutants, ROMs, RAM-free capture receipts, PCM and
source/core hashes are retained. Instrumented good PCM equals normal core.
Run554 first exposed that the wrapper did not yet handle the correct
padding rejection as a negative result;556 and fresh source-bound558 do.
No production receiver change was needed.496 Python tests pass.

## Complete-game transport proof and remaining failures

`camera-triple-full-553` completes9,404 fixed-input frames, matching normal
`camera-triple-fixed-550` in every timeline row and PCM byte. Provenance560
checks209,139 actual logical bytes and218,232 physical SPC stores across
9,093 packets: no mismatches. CPU writes, all received bytes, header fields,
key-on schedule and ready events pass. Last-logical-byte-to-ready takes
169–1216 SPC ticks (includes padding receipt). This is not acoustic or
physical audio certification. Full-neutral557 has no late NMI interval in
the observed7600–8420 window.

The full8,701-frame renderer capture557 is observer-neutral, but strict
split audit559 **fails coverage**: eligible frame2119 has none of the160
required street-line records. Other frames are not substituted and the
gate is not weakened. No split-free claim is made for this candidate.
The missing renderer frame needs an exact transition trace before interpreting
it as a display bug or observer eligibility mismatch.

Next: combine independently proven cost reductions only when actual deadlines
improve; investigate publisher/phase scheduling and remaining main work.
Keep loading/renderer failures visible and continue acoustic diagnostics.
Review: `http://127.0.0.1:8766/triple-review-561/`.
