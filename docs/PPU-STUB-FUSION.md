# Full PPU write-stub fusion

The caller already saves A/P and masks interrupts. Four private handlers now
reuse that ABI instead of repeating the dispatcher's saves and register decode.
Only the JSL operands of18 exact static PPU write stubs change, across eight
mirrored banks. Ordinary RTS tails, coroutine JMP tails, mailboxes, NMI policy,
and unrelated generic I/O remain byte-identical. The helpers preserve X/Y/D/DB
and restore the dispatcher's hidden B=$1B convention before returning to PLA/PLP.

This is a measured local optimization, **not a fix for the remaining slowdown**.
Neither candidate is promoted. Keep phase-balance2769 as the offline baseline;
Rival's last deployed2648 cartridge, splash, SNAC settings and OBS are untouched.

[Audition, frame collage and bound results](http://127.0.0.1:8766/ppu-fusion-review-2887/)
includes the failures alongside the improvements.293 source bindings,16 served
artifacts and three exact, unnormalized replay WAV copies were checked. Both
route captures separately verify completion and the expected cartridge hash.
The page was rendered and visually inspected.

## Candidates and executed correctness

- Fusion2868, parent2769:
  `208c0c712c832ed78cff1c626ce90e79c31a31756a060c8315baae79eaa36d80`.
- Fusion plus tile-cache2869, parent2814:
  `addf5a75f3ac767d74b603dadf5af6bf0de9fedd7bf91158649c124d28df6095`.

Oracles2870 and2881 each execute432 complete before/after stub pairs, comparing
all128 KiB WRAM except dead stack bytes and heartbeat counters. Independent
expectations check the PPU state, mailbox, A/B/P/X/Y/D/DB/SP and actual NMI
delivery. Cases cover all18 stubs, all eight banks, both latch states, changed
and unchanged CHR selection, ordinary versus coroutine returns, depth/pair/task
ownership, active scanout and pending VBlank. Each rejects four executed
mutants: bad address mask, missing CHR dirty, bad scroll toggle, and lost B.

The fixture redirects the original coroutine resume destination into its ABI
recorder; it does not pretend to execute the later coroutine task there.
Separate integration runs cover the real game. Stack positions20/80/FF are
explicitly scoped, not a claim about every emulation/native stack-wrap edge.

Timing2875 executes all18 stubs with two input/latch cases each, measuring entry
through actual return. Normal and observed full WRAM match. Savings are444–592
master clocks, approximately36–46% of these complete calls. Beam-wait costs
are excluded from this masked active-display measurement. No whole-game
percentage speedup is inferred.

## The same-state regression still fails

Both90-frame replays2871/2872 begin at checkpoint2233 from the authenticated
2839 capture and passing same-ROM control2844. The guard rebuilds the entire
candidate composition and requires exact ROM/helper equality. It rejects
checkpoints inside modified stubs/helpers and retains both actual pad streams.

At2239, neither trial advances the interrupt count or game completion; the
update still finishes on2240. Pictures match the parent through2240. PCM starts
differing at2235; it is not called identical or acoustically better. The replay
runner's successful process exit means a valid comparison, **not recovery**.

## Fresh-boot combat and rendered scrolling

| Variant | Running/jumping combat | Park camera short irregular holds |
| --- | --- | --- |
| Fusion2868 |1751 two-frame intervals; one three-frame stall2236→2239 |0 east;0 west |
| Fusion+tile2869 |1753 two-frame intervals; strict test passes |0 east;2 west |

These summaries include original-NMI-busy frames; they are not dropped from
the denominator. All other/excluded/censored intervals remain in the report.
Fresh encounters are not the same workload as the saved-state regression.

Full routes2876/2877 complete9224/8940 frames. Renderer observers2878/2879
match their independent normal runs. Audits2882/2883 find no split, stale-camera
or coverage failures, but that does not erase the combined candidate's one
one-frame and one three-frame westbound camera hold. Longer14-frame holds
are retained: fusion east10/west3; combined east8/west7.

Instruction control2880/window2884 is neutral across the full4927-frame run.
In its fresh encounter, the long original interrupt body runs from2236
line211:1244 through line255:1320 (60088 clocks), leaving time for the next
pending interrupt. This is not a matched-clock explanation of the unchanged
old-state failure. A normal serviced interrupt can cross the frame boundary;
boundary crossing alone is not proof of a lost VBlank.

Full unit suite:1208 tests pass (`/tmp/rcr-tests-2885.log`). Five new tests
cover exact caller preconditions/edit scope, every bank's rejection guards,
matrix coverage, independent ABI/NMI fault sensitivity, and in-flight replay
rejection. `git diff --check` passes.

## Next constraint

Local write/copy savings have not recovered the known masked-interval failure.
The next investigation needs causal instruction timing from that restored
state, with a fresh relative clock and a neutral replay control; historical
global trace counters must not be reused after restore. That can distinguish
remaining work cost from the scheduler's service policy before attempting an
interrupt collector that preserves every real event exactly once.

No new full menu, DSP transport, main-to-display latency or physical gameplay
qualification is claimed. Gameplay audio fidelity/pop-free operation, overall
NES-speed parity and scrolling acceptance remain open.
