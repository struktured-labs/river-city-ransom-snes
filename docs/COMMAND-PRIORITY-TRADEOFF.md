# Command stall measured; local fix does not improve the route's worst gap

Current qualified graphics experiment remains3955. Neither trial below is
promoted or deployed. Physical-console and acoustic acceptance remain open.

## Actual SPC execution

New read-only core3991 inserts one host-only opcode-entry observer. It uses the
existing monotonic SPC clock, raw CPU input registers and raw SPC output RAM;
it never reads consuming timer MMIO or changes emulated state. Failed build3990
is retained (register member names corrected before the fresh3991 build).
3991 build12.490s. Control3992 matches the old core's complete9,090-frame primary
timeline/native PCM; observed3993 separately matches the exact same core.
Replay23.421/23.606s; totals28.366/29.344s including post-capture verification.

Bounded observation144726000–144778000 SPC ticks records three complete D7
commands taking84,772,118 SPC clocks from first observed pending input to
acknowledgement. The long command begins144760229 at08B7. At144760262, CALL0477
enters idle3455; poll3272 advances timers/sweeps and then publish3309 executes
both pulse voices. Acknowledgement is visible at144761001/0485. This confirms
the idle-work hypothesis for this window, not every audio disturbance.

## Two actual cartridge experiments

-3994 (`ba0a8ec77362b969d99be11534edb0d60ba0634f7a82eb0a60623e7f89f9be23`)
  checks pending D7 before all idle work. Executed continuous timer tests3995
  fail three cases: deadline offsets reach1794/1538/1863 SPC clocks against the
  existing1400 limit. Rejected without a gameplay campaign. Timer-drop and
  legacy-volume-writer negatives also fail as required.
-3996 (`caf6dad312f4bd1d8009dfee849d26657d128472a35d52002831eb30c0577ae3`)
  keeps poll3272 and conditionally skips only old-state publication. The13-byte
  helper fits verified padding3523–352F, leaving receiver3530 unchanged. Fixed
  engine/upload length and all non-audio code remain unchanged.3997 passes all
 16 parent/trial executed cases (101 packets plus one second idle; both modes,
  four sender delays), with timer-drop/legacy-writer negatives rejected.

Fresh full3998 and neutral audio3999 retain8641 packets,1588 restart checks,
4,846,034 stereo samples and no clipping. All four classified room populations
remain two-frame game iterations. Full input delivery and game counters match
3955. There are26 changed pictures, one camera-RAM sample and8114 sampled game
RAM differences; all are retained in4002, not claimed equivalent gameplay state.

Neutral CPU4001 (23.358s replay) shows8486 command wait16176→4982 master clocks.
Other neighboring waits increase:8484 1616→2012;8485 1814→2078;
8487 2488→4098. These are elapsed CPU intervals, not exclusive SPC execution.
The targeted8485→8486 packet gap improves20.857717→20.385651ms, but the route's
worst gap becomes21.037180ms at8531→8532. Minimum12.049391ms versus12.147901;
peak6469 versus6336; largest adjacent PCM step4607 versus4556. Neither adjacent
step size nor command timing establishes audible popping or pop-free sound.
Audio analysis4000 took28.208s. No gain in worst-case pacing; do not promote.

## Next action

Keep3955 as the graphics baseline. Compare the original-driver and packet-send
budgets across the boundary/normal-IRQ alternation at8531–8532 before proposing
another scheduling change. The remaining jitter is not explained by command
acknowledgement alone. Do not skip continuous sound work or adjust audio to hide
gaps; preserve complete native PCM and original game iteration cadence.

[Raw stall, every changed picture, and trial tradeoff](http://127.0.0.1:8766/command-priority-review-4002/)
· [Native trial audio](http://127.0.0.1:8766/command-publish-priority-audio-review-4000/)
· [Audio issue6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6).
