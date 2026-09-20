# Boundary-service tradeoff is real; inactive overhead is not its cause

Parent/trial raw-state observations3741/3742 independently reproduce all2579
primary prefix frames and native audio exactly. Each retains157 post-frame
WRAM/VRAM snapshots, frames2396–2552, with no emulated memory writes.

Audit3746 validates both observer/control/source chains against visual review3740.
Original nametable shadows match in156 of157 frames; frame2413's complete source
byte differences are retained. All26 changed-picture frames have equal original
nametable shadows. Among their differing supported first-nametable text words:

-27 trial words already equal the current original shadow while the parent lags.
-34 parent words equal the current original shadow while the trial lags.
- Frame2408 has no corresponding first-nametable word change and remains unresolved.
  Its744 differing pixels occupy scanlines186–188, so frame-end tile state alone
  cannot establish the mid-frame cause.

The differences include mixed dialogue publication and later player-name/health
publication at2473/2485. A faster sound service has not earned permission to delay
graphics. `no_publication_regression` is false. Three unit tests reject changed
source/short snapshots and distinguish regression, improvement and unsupported
attribute changes. Every changed-picture frame and all source differences remain
in `build/overflow-3526/boundary-publication-audit-3746/report.json`.

## Follow-up experiment3743

SHA256 `976c2bacbdd9950cda35d07d608709e3366bcb483bc81bcb546d0dc49dec7157`.
Add a20-byte fast entry in verified free7BE0 padding. When pending is zero it
preserves P/A (hidden B untouched) and rejoins camera work without the full
context save. When pending is nonzero it restores P/A and enters the unchanged
guarded helper from3737. No new service policy or weakened guard.

Fresh normal3744 and finalized observer3745 are neutral. Observed replay6.711s,
whole observer wrapper7.325s. Actual stable packet spacing improves further to
11.190–22.105ms, versus parent9.852–23.707ms.2179 packets per arm; native raw DAC
equals delivered PCM. Original game-counter/input trajectories remain identical.

But every picture is byte-identical between3737 and3743, including all26
differences from3695. Removing inactive context overhead did not fix the visual
tradeoff. Do not expand qualification or deploy either trial yet.

Review3747 JSON has current hashes, complete intervals, exclusions and audio
artifacts. Its generated HTML retained a legacy3737 heading from the reusable
reviewer; do not cite that page as correctly labeled3743 evidence. Original
review3740 remains the correctly labeled3737 before/after gallery, and also
contains exactly the same changed pictures observed in3743.

Next: trace actual tile preparation/transfer timing around2473/2485 and the
scanline boundary at2408. Investigate active service placement or publication
ordering, not further inactive-overhead tweaks. Full CPU-state verification of
the new boundary entry, broad speed/scrolling/audio and hardware acceptance stay
open. No cartridge promotion or MiSTer deployment occurred.
