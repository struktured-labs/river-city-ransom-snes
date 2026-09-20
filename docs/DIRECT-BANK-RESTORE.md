# Direct bank restoration: measured CPU saving and completed sweep

Candidate `build/bank-restore-on-405/native-cpu.sfc`, SHA-256
`7b52e63d0e6f62d2656303baababdbe96f34b376c9dd13e141b9f0f177ae0fb1`,
is **experimental and not deployed**. It completes the controller-only park
sweep and improves room-1 fade timing, but one actual scrolling mismatch,
first-room loading, broader combat/endurance and acoustic fidelity remain open.

## Change and exact-state tests

Original `$FF29` restores R6/R7 and the mapper selector through five translated
generic mapper writes. Default-off `experimental_bank_restore` replaces this
pinned 38-byte original routine's entry with a direct, NMI-protected helper.
It retains FC/FD/FB, the mapper shadows, the port's existing R6-based paired
mapping, data/program bank return, CHR dirty policy, final A/N/Z, other flags,
X/Y/DP, caller stack and interrupt-owner counters. The final diagnostic mailbox
and R6-write counter also match. Internal jump scratch is private to the helper.
Masking begins before any partial mapping change; pending edges are not read or
acknowledged by the helper. The normal guarded re-enable policy runs only after
the restored bank is active. The raster-scheduler combination is rejected.

`bank-restore-off-405` is byte-identical to parent direct-APU candidate 397:
`d64e388310cdc2cd0680d4125a27038c52ce9c7933bf504a14a41eebdacc5340`.
No game timers, graphics, sound data or SPC code changed.

`bank-restore-oracle-408` passes **16,896 executed paired comparisons** against
the original five-write sequence using actual generated mapper stubs, followed
by an independent host state oracle. Coverage includes every R6 byte, all eight
source/target banks, four final selectors, varied R7 values, and both CHR-dirty
policies. Caller decimal is clear and DP is zero in this fixture.

512 cases additionally wait for a **fresh real masked hardware NMI edge**.
Exactly one interrupt must be delivered only when both ownership guards allow
it; inhibited cases must deliver none. A small synthetic handler acknowledges
the real edge and returns through the restored program bank. Caller state and
stack must still match. This is emulator-executed edge coverage, not a physical
hardware or full-game NMI-body certification.

Seven deliberately broken variants are rejected: wrong program bank, wrong
data bank, lost CHR dirtiness, wrong R7, lost flags, clearing a pending edge,
and ignoring interrupt ownership. The initial 404 fixture failed to assemble
because of an incorrectly parenthesized long-jump expression; it is retained
and is not counted as an executed test. The corrected matrix and all seven
mutations above execute successfully or fail their intended runtime oracle.

`bank-restore-timing-409` measures 96 matched-state calls through real banked
JSR/RTS boundaries: **6,016–6,288 master clocks saved per call**. Full observer
WRAM matches the normal core. The game trace independently measures the
FF29-to-packet-sender stage at 1,070–1,178 clocks across 689 samples, versus
approximately 7,272 clocks in the earlier exact missed-deadline samples.
These are elapsed costs, including refresh/events, not full-game speed parity.
441 Python tests pass; `git diff --check` is clean.

## Fresh whole-route evidence

| Evidence under `build/` | Result |
| --- | --- |
| `bank-restore-background-audit-408` | **Overall FAIL**. Both routes now complete. 753 common camera positions (259/113/111/270); one park background mismatch remains at camera 240, plus a frame-end publication warning and settling failures. Both background observers remain neutral and the known broken control still fails. |
| `bank-restore-single-normal-406` | Controller-only sweep completes in 8,807 frames, versus NES 8,548. No injected health, rescue input or changed timeout. This is not combat-speed equivalence. |
| `bank-restore-entry-408` | **FAIL**. First scenery 8/7/7 versus NES 7/7/7; whole loads 24/30/29 versus 20/31/30. Room 1 now differs only at fixed offset 7; its later fade steps match. Rooms 2/3 match all forty fade checkpoints. |
| `bank-restore-park-audit-408` | Scoped stable unpaused park packet cadence passes, with no interval over 1.5 frames or native faults. |
| `bank-restore-audio-408` | All 9,223 completed-NMI packets match CPU writes; no unfinished tail or unflushed writes. Full PCM/gap clips retained. Not a pop-free verdict. |
| `bank-restore-neutral-spans-411` | All 9,408 fixed-route timeline rows and PCM match normal execution; no late NMI-entry interval in the observed window. |
| `bank-restore-status-audit-411` | Both Present Status entries have zero pixel differences and correct numeric values. |

Settling failures are retained, not described as literal thousand-frame visual
stalls: some positions are first seen moving through and only receive their
first second-consecutive sample when revisited on the return trip. Neither
sample selection nor the existing acceptance policy was changed.

## Remaining scrolling error and boundary warning are different

`bank-restore-render-audit-412` binds a new renderer replay to the exact same
8,807 normal timeline rows and PCM, and to independent CPU observation.
At camera 240, NES frame 7604 draws 240 throughout the playfield. SNES frame
8670 draws **242 on lines 32–158**, then **240 on lines 159–191**. The actual
camera hook arrives at **line 38, cycle 528**. The unshifted images differ at
2,921 fixed-strip pixels and 6,849 expanded-playfield pixels. This remains a
real missed street deadline, not an accepted image alignment.

`bank-restore-camera-audit-412` attributes this exact interval: NMI-to-driver
20,090 clocks; original sound processing 41,482; bank restoration 1,136;
sender-through-camera 19,590. The NMI interrupts the JSR at F29F, immediately
after E095's camera calculation and before FAE9's camera-bound clamp.
Previewing DC/DD before that clamp would be unsafe: the original bank-0
B9B0 routine can still modify both. Further speed/scheduling work must preserve
that ordering or prove equivalent results, not publish a guessed camera.

The separate frame-end warning is frame 6699 (room 2, game camera 9, table 7).
`bank-restore-edge-410` shows the camera hook at line 239/cycle 1224, an NMI
edge crossing before the table store, then the store at next-frame line 13.
The new renderer trace (`bank-restore-raster-411.csv`) shows old scroll 7
throughout frame 6699's street and new scroll 9 throughout frame 6700's street.
That warning alone does **not** demonstrate the same mid-frame split as frame
8670. The strict publication gate is still failed; it has not been relaxed.
Do not assume moving an interrupt mask fixes the remaining visible error.

The next candidate still needs original-speed room-1 loading, a clean full
scrolling run, broader combat/endurance testing and self-audited gameplay
sound before a Rival restart.
