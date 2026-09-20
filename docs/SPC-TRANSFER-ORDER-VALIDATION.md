# SPC receiver ordering: data must precede its token

Retained candidate `build/audio-data-first-02/native-cpu.sfc`, SHA256
`227dd74494a458fbc97baffb25fc4281601405994822c709f583afa42f188804`.
The initial `audio-data-first-01` ROM is byte-identical; version 02 records
the shared sender include in its source manifest.

## Fault and correction

The legacy sender announced byte index Y on $2140 before loading/storing
that byte's data to $2141. At byte zero, a 16-bit STY also cleared port 1.
The pinned SPC receiver waits for the index, immediately reads port 1, and
stores that value at $40+X before acknowledging. Its original source and
binary agree (`E4 F5 D4 40`, post-operand PC $048F). If the CPU pauses
between announcing the index and supplying data, the SPC can consume the
previous byte and still acknowledge correctly. CPU-side data/ACK auditing
alone cannot detect that corruption.

The corrected sender stores data first, then announces its index, then
waits for the acknowledgement. `snes/native_spc_frame.inc` is now shared by
the native game and diagnostic. The DSP engine itself is unchanged.

## Executed causal regression, not a gameplay-popping verdict

`tools/check_spc_transfer.py` adds 32 CPU NOPs before each data write.
Both variants use that same delay; the negative restores the old order.
The host-only receiver observer records actual SPC store operands, without
emulated reads/writes/cycle changes. Its reproducible insertion fragment is
`tools/snes9x_spc_receive.inc`, used inside `SMP::op_write` before `tick()`
in the pinned Snes9x source; rebuild smp.cpp after inserting it.

`build/spc-transfer-regression-02/index.html` retains both full WAVs,
every mismatch, logs, ROM/core/source hashes and strict receiver audits:

| Delayed transfer | Compared bytes | Wrong bytes | Signal test |
| --- | ---: | ---: | --- |
| Data first | 7843 | 0 | Pass |
| Old token first | 7843 | 1923 | Fails: no sustained waveform |

An independent normal-core run matches the corrected observer's complete
timeline and WAV byte-for-byte. Failed signal PCM is now saved before the
smoke test raises its failure, so negative evidence is not discarded.
Three receiver unit tests reject stale bytes, malformed/reordered values,
wrong receiver PC and incomplete streams. All 116 Python tests pass.

This demonstrates an ordering bug under a controlled CPU delay. It does
**not** establish that the same race caused the user's reported popping.
The original-order short game replay `receive-parent-01/snes` had zero
mismatches across 42665 bytes and matched its normal-core timeline/WAV.
The corrected short replay also had zero mismatches across 42665 bytes.

## Game and sound validation

Short baseline remains 1963 frames, transition durations 165/57/60/481;
settings/story still fail the original-speed gates. The corrected long
shop-exit route remains 7559 frames. Café fixed menu pixels/CHR and room-3
fixed camera/scroll strip checks pass. Normal and receiver-observed long
captures have byte-identical timeline and WAV.

Actual SPC receive comparison covers 169280 bytes in 7360 packets, with
zero mismatches. Ordered bus/ACK auditing verifies one packet per completed
NMI and no unfinished tail/pending CPU writes. Completion-gap histogram:
1:7335, 2:5, 3:6, 4:3, 7:4, 8:1, 22:4, 32:1.
Full PCM/gap review: `build/data-first-long-audio-audit-01/index.html`.

Isolated pulse, triangle, periodic-retrigger, sweep-reload and gated
disabled-reload probes pass with the corrected shared sender. The broader
length-expiry probe **fails**: active phases retain approximately 1914 RMS
instead of expiring to silence; the explicit disable phase is silent.
Evidence is retained at `build/data-first-probe-length-01/report.json`.
Earlier `audio-length-01` and `audio-length-final-01` reports have the same
failed phases (0/2/3) and passing explicit-disable phase; this is a
reconfirmed pre-existing limitation, not a newly established regression.
The transfer-order correction does not resolve that synthesis failure.
These scoped tests do not certify all synthesis behavior, full-game speed,
all scrolling encounters or perceptual popping. Rival was not reloaded.

## Natural long-route negative finding

The old token-first ROM was also replayed with the receiver observer over
the complete shop-exit route: `build/token-first-long-01/snes`, 7559 frames.
`build/token-first-long-receiver-audit-01.json` reports **zero mismatches
across 169257 bytes / 7359 packets**. Its timeline and WAV are byte-identical
to the earlier uninstrumented `attribute-batch-long-normal-01/snes`.
Thus neither the short nor long natural emulator run reproduces receive
corruption under old ordering. The controlled-delay counterexample remains
valid, but must not be cited as proof of the reported gameplay popping.
Further investigation must consider cadence/synthesis and hardware behavior.

The corrected ROM additionally passes the explicit 32-frame rightward
movement comparison against original NES: `build/data-first-movement-audit-01`.
This is still a narrow stationary-camera movement test, not full-game speed,
combat, all scrolling or loading certification. No hardware deployment.
