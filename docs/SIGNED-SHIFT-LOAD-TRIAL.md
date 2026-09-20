# Signed-shift load optimization: measurable saving, rejected graphics timing

Review: <http://127.0.0.1:8766/signed-shift-review-1957/>

Offline candidate `build/signed-shift-trial-1947`:
`5f72311e1663664afd31fdbd608d9fbc9389197f07a84a43699305ecfca6a9ad`.
Parent is the receiver-dispatch trial `ec1c1ca53d65`.
**Not deployed; Rival and OBS were not changed.**

## Implemented change

`tools/build_signed_shift_trial.py` replaces the exact 17-byte block at
`$C3B9..$C3C9` in all eight replicated game banks, plus the SNES checksum.
It uses CMP/ROR for sign extension instead of AND/LSR/ORA/STA. Final A, X,
flags and the shifted word are preserved. No new code allocation, asset,
sound engine, fade-counter, controller or interrupt-handler change.

The initial `LDX #5` and the loop-body entry address `$C3BB` remain in place.
That second entry matters: the original `$C395` BMI enters `$C3BB` with X=0
38 times in this school-load replay, executing 256 shifts each time. The
source NES ROM has that same branch; this is not attributed to a port error.
The optimized body retains the count behavior, including wraparound.

## Executed oracle and harness

`build/signed-shift-oracle-1956/report.json` passes **589,824 cases**:

- All 65,536 input words crossed with D/I/V flag combinations, one combination
  per replicated bank: 524,288 five-shift cases.
- All 65,536 words entering the body directly with X=0 and P=$7D: 256 shifts
  per call, matching the additional entry observed in the real trace.
- Compare operand bytes, A, hidden B, P, X, Y and stack after actual Snes9x
  execution. Emulation mode, DP=DB=0, hardware interrupts disabled.
- Logical instead of signed shift, incorrect final A, and incorrect final
  zero flag are all rejected as executed mismatches, not build failures.

This is not an injected-interrupt proof or exhaustive arbitrary body-entry
count matrix. The initial five-shift-only oracle1946 was insufficient for the
observed extra entry and is superseded. Fixture assembly/include/range/header
failures1944/1945 and a refused 32,000-frame invocation1955 are retained;
the successful invocation stays within the existing 30,000-frame harness cap.

New `tools/capture_combat_instructions.py` gives each instruction window a
fresh same-core uninstrumented control, complete timeline/PCM equality and
source binding. It refuses inherited observer overrides and changed inputs.
New profile tests ensure direct body entries cannot disappear from call
accounting. **998 unit tests pass**, log `/tmp/rcr-tests-1958.log`.

## Real-game measurements

Parent controls1941 and instruction captures1942/1943 cover the unchanged
running-jumps policy. Trial normal/observed main captures1948, instruction
control1950 and instruction capture1952 repeat that policy. All observation
pairs preserve their complete normal video/RAM/input timelines and PCM.

| Measurement | Parent | Trial |
| --- | ---: | ---: |
| Alley transition loop | 15 frames | 15 frames |
| Return-to-school loop | 27 frames | 26 frames |
| School loop elapsed master clocks | 9,669,532 | 9,314,156 |
| Shift blocks, total 45 calls | 1,709,764 clocks | 1,308,884 clocks |

Seven calls use the five-shift entry and 38 enter with X=0. Both builds execute
9,763 shift iterations in the measured school interval. The shift blocks save
400,880 elapsed master clocks; the whole observed loop saves 355,376. These
are instruction-entry elapsed costs including boundary events, not exclusive
CPU cycles. Different execution timing can change other work and encounters;
the whole-loop difference is not attributed solely to this block.

Trial running-jump cadence still **fails**: the retained outliers are frames
2559–2574 (eight NMI ticks) and4176–4202 (seven ticks). No transition waiver.
Three native PCM excerpts and exact captured frames are included; no acoustic
benefit is claimed. The premature profile1954 counted only the seven obvious
entry calls in its inclusive-call subtotal;1957 includes all45 and supersedes
that report. Own-region cost was unchanged by this accounting correction.

## Graphics regression prevents promotion

Fresh full-route capture1949 completes 8,936 frames. Its shorter route length
than the parent is not an equal-work speed ratio. The unchanged NES oracle
in [room-entry1953](http://127.0.0.1:8766/signed-shift-entry-1953/) finds:

| First scenery latency, rooms1/2/3 | NES | Trial |
| --- | --- | --- |
| From rendering enable | 7 / 7 / 7 | **8 / 6 / 7** |
| From room change | 20 / 31 / 30 | 20 / 26 / 27 |
| From rendering off | 20 / 31 / 30 | **21** / 27 / 28 |

Alley visibility is a frame late after enable and rendering-off. Alley and
mall fixed-offset fades differ; park matches all40 offsets. The faster mall
fade is also a graphics-timing mismatch, not an automatic pass. Existing
thresholds and original references were not changed to accept the trial.

All67 served artifacts across reviews1957/1953 were HTTP/hash verified;
44 source bindings and all three native sample slices were rechecked.

Next: trace the trial's first alley/mall main-to-fade/producer schedule against
the parent, retaining whole-load and fixed-offset graphics gates. Do not
promote the arithmetic optimization until scheduling, complete scrolling,
menus and audio have fresh passing evidence. Physical rare slowdown and
nonzero audio pops remain open.
