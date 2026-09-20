# Faster sound-register writes: verified saving, not a scrolling fix

Candidate `build/direct-apu-on-397/native-cpu.sfc`, SHA-256
`d64e388310cdc2cd0680d4125a27038c52ce9c7933bf504a14a41eebdacc5340`,
is **experimental, not promoted or deployed**. It reduces sound-driver work
without changing the SPC engine, sound data or graphics. Full scrolling and
original-speed acceptance still fail.

## Measured cause and change

The parent 373's two missed camera deadlines are now instruction-bound in
`camera-late-east-audit-401` and `camera-late-west-audit-401`. Entire 9,953-frame
replays and PCM equal the normal capture, including the death/route timeout.
Immediately before the late camera, original sound processing takes
34,354 / 47,636 master clocks, bank restoration 7,272 / 7,274, and the
sender-to-camera interval another 20,092 / 19,052. That last interval includes
packet transfer, return and remaining game work; it is not exclusive audio
cost. Frequent dynamic sound writes were paying for two ABI save/restore
layers plus generic hardware dispatch.

Default-off `experimental_direct_apu` specializes only the checked dynamic
STA helper for `$4000..400F` and `$4015`. Its stub **masks NMI before reading
the mutable `$07F9/A` address**, classifies it, and preserves the original
status/value across the decision. Other addresses use the entire unchanged
generic stub, including its mapper bank-return handling. The direct helper
preserves A/P/X/Y/DP/DB/PB/stack, maintains the existing mailbox, records
ordinary `$0A00,X` writes for the bus observer, and applies the same enable,
length-eligibility, timer-reload and note-retrigger rules. Its lookup uses an
explicit long ROM address, not the data bank's low I/O address space.
The existing guarded interrupt-enable policy is retained. Raster-scheduler
combination is rejected; it has not been qualified.

`direct-apu-off-389` is byte-identical to parent 373. Initial candidate 389
had a wrong-bank table lookup. Candidate 393 also lacked masking before
classification; review caught that race before promotion. Neither is eligible.
397 includes both corrections. No emulator timing override is used.

## Independent executable checks

`direct-apu-oracle-401` passes **6,144 paired legacy/direct cases** plus an
independent host state oracle: all 256 values at the 17 specialized registers
and seven generic fallback addresses. Cases vary initial enables, length
eligibility, flags and caller P (including decimal/carry), with nonzero DP and
mirrored DB. Every call compares all 24 APU-shadow bytes, eligibility and
caller state against the original stub. Five real mutants fail: missing timer
reload, disabled-channel reload, lost enable-clear, wrong lookup bank and
wrong written value. Unit tests additionally exhaust all 65,536 addresses
through the generated branch destinations and require masking to be first.
This fixture does not certify real NMI-edge timing or DSP/acoustic fidelity.

`direct-apu-timing-401` observes 80 matched-state calls through real JSR/RTS
boundaries. The 68 specialized calls save **466–1,110 master clocks each**.
The 12 fallback controls cost 206–286 additional clocks; that tradeoff is
retained in the report. Observer and normal full WRAM are identical.
438 Python unit tests pass separately.

Fixture development failures are retained, not counted as passes: header
overflow, a too-short diagnostic runtime, a WRAM-bank polling mistake, an
include-path mistake that prevented mutations from being applied, correlated
seed data that concealed disabled-reload corruption, and an aliased timing
label. The corrected final runs above execute the actual mutated source and
reject all five broken variants. Diagnostic duration was extended for its
6,144-case workload; the game navigation timeout was never changed.

## Exact-candidate game regressions

| Evidence under `build/` | Result |
| --- | --- |
| `direct-apu-background-audit-400` | **FAIL**. 700 common positions (259/114/110/217). Park cameras 217 and 303 differ by 2,967/3,166 pixels in the fixed strip and 6,898/8,256 in the larger playfield. Both observers remain neutral; known broken control still fails. |
| `direct-apu-single-normal-399` | Return route still times out after death/respawn at 9,953 frames. No recovery inputs, health writes or timeout extension. |
| `direct-apu-entry-400` | **FAIL**. First scenery 8/7/7 versus NES 7/7/7; whole loads 24/30/29 versus 20/31/30. Rooms 2/3 fixed fades match; room 1 differs at offsets 7/11/15/19/20 (parent differed at 7/11/15/19). |
| `direct-apu-park-audit-400` | Scoped stable, unpaused park packet cadence passes; no gaps over 1.5 frames or native faults. |
| `direct-apu-audio-400` | All 9,222 completed-NMI packets match CPU writes; no unfinished tail or unflushed writes. Full PCM and gap clips retained. Not a pop-free verdict. |
| `direct-apu-neutral-spans-403` | All 9,408 fixed-route timeline rows and PCM match normal replay. No late NMI-entry interval in the observed window. |
| `direct-apu-status-audit-403` | Both Present Status entries exactly match NES, including numeric values. |

The old camera-255 failure now matches at the same selected frame, but camera
371 is absent from the new common sample set and is **not claimed fixed**.
Two failures at other positions remain. A helper speedup is not a global
deadline guarantee; the remaining pre-camera work and variable audio cost
still need improvement. No restart until a candidate meets the user's
original-speed and regression requirements.
