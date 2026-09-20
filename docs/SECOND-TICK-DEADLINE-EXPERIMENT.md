# Retained graphics deadline: isolated fix, route regression

Default-off `experimental_second_tick_deadline` requires
`experimental_second_tick_prepare`. It changes only the camera-tail service
call and appends a helper: read the real nine-bit beam, service before line194,
otherwise retain ownership for the existing interrupt-exit fallback. No change
to controller mapping, sound engine, artwork, or live Rival cartridge.

## Executed evidence

- `build/second-tick-deadline-oracle-755/report.json`: 36 cases across the
  cutoff, late active display, VBlank and high-bit scanlines, with cycle-burning
  graphics-bridge spy. Active-display cases receive exactly one NMI on line240
  and exactly one service, preserving X/Y/DP/DB/SP. Four mutants are rejected.
  The unguarded line231 control executes through the whole VBlank and observes
  zero NMIs before next-frame line60, reproducing the original failure.
- Initial fixture752 only checked interrupt count; its larger synthetic work
  allowed an early-case interrupt to arrive late. Fixture755 strengthens this
  to check actual NMI entry line and early completion before240, using a
  roughly42-line CPU workload. Neither fixture proves a production worst-case
  graphics budget. Keep752 as historical evidence, not the final qualification.
- Disabled rebuild755 is byte-identical to combined735. Enabled unbranded752
  differs by276 bytes, with all73 existing global runtime symbols unchanged.
  Cartridge SHA256:
  `59e5b522e529a8f437330ab1ece52f54d5e92c7dc0ca1515e8655f1414c4f3bb`.
- Unbranded normal/renderer754 agree over all9,097 frames. Branded753
  normal/renderer754 agree over all9,402 frames. This is observer neutrality,
  not equivalence to the pre-guard game execution.

## Full-game replay rejects promotion

`build/second-tick-deadline-holds-756/` retains every interval and long stop.
Unbranded short irregular holds rise from0/0 east/west to12/24. Branded rise
from6/7 to12/25. One/three pair counts are6/10 for both guarded cartridges.
Do not use passing isolated mechanics to overrule this regression.

Branded renderer755 covers all7,784 eligible frames, with no splits or missing
coverage, and6,839 unchanged-camera checks with no extra stale hold. Entry755
passes all first-visible latency gates but still fails exact fixed-offset fades.
There is no new guarded-cartridge background/audio/hardware qualification.

CPU756 is neutral against the complete branded normal timeline and PCM.
Start757 and work757 bind the cartridge, labels, actual instructions and NMI
events. The captured window7768..7792 has an observed NMI at line240 in every
frame, yet original actor/main work can still cross that boundary:

- Main begins7776 line51 and stores camera122 at7777 line33.
- The adjacent camera stores are120 at7774 line224 and124 at7778 line222.
- Renderer shows them at7775,7778,7779: the producer itself now has3/1 spacing.

The actor call in that iteration contains70,066 clocks of observed ordinary
NMI work. Outside that interrupt it takes161,880 clocks, versus162,104 and
162,026 in the neighboring iterations. It starts later (line122 versus102/100);
do not mislabel the longer elapsed call as intrinsically more expensive AI.

This distinguishes the next problem from the previous masked-over-VBlank
failure. Also, fallback service is followed by ordinary preparation on some
interrupt exits; both calls are real and should be budgeted. Coalescing them
without proving row/CHR/palette-generation latency would be unsafe.

Next work: bound pre-camera actor/sprite cost and graphics service accounting
together. Do not merely move a scanline cutoff until one screenshot looks good.
588 unit tests pass. No restart or release claim.

Web audit: `build/early-main-review-751/index.html` (served on local port8766).
