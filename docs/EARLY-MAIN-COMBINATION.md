# Early-main combination: smoother, not promoted

The combined cached-controller, fused-sprite-position and second-tick producer
experiments substantially improve rendered cadence. They are still default-off;
Rival has not been restarted with these cartridges.

## Evidence through run 750

- Unbranded735 SHA256:
  `ad36c2eace12cc815c7770a96ea0ba2d9bdd57ba0f6921a9dbed634a151fc3db`.
  Normal/renderer736 are neutral over all 8,568 frames. Renderer738 checks
  7,255 eligible frames with no splits and 6,295 unchanged-camera frames with
  no stale publication. Uniform-holds748 finds zero short irregular holds in
  both directions, retaining long stops separately.
- This is not full qualification: first-room visibility takes 21 frames versus
  NES20; fixed-offset fade comparisons fail. Background-audit742 matches all
  646 selected backgrounds, but room1 has only 24 samples (minimum64), and
  late-publication/settling gates fail. Status742 and movement742 pass their
  bounded scenarios, not full-game speed.
- SPC-audit742 verifies 8,296 packets and actual received writes. Transients746
  passes existing digital limits and rejects injected spikes/missing callbacks.
  Whole-route maximum sample step is 3,120/32,768. This is not a perceptual,
  hardware, or pop-free verdict. The separate noise-clock correction is absent.
- Branded744 SHA256:
  `0e10df245dafa98d2b9b0ea3dd1445bdcddc63877b9514053502fad1e64e8158`.
  Original supplied branding and ident are unchanged. All 8,899 normal/renderer
  frames agree. First-visible latency passes all three room gates (20/29/28
  frames from room change; seven frames from render enable), but fixed-offset
  fade comparisons still fail. No full branded background/audio qualification.
- Counting paired 1/3 holds alone missed a problem: branded744 has zero pairs
  but six east/seven west isolated three-frame holds. Stronger uniform-hold
  audit748 retains every short irregular hold with equal two-pixel endpoints;
  this is not an assumption of equal intended motion or identical enemy work.

## Confirmed interrupt failure

`build/early-pad-position-missed-vblank-750/index.html` binds the instruction
trace, NMI events, renderer trace, cartridge, and seven raw screenshots.
At frame7695 line231, camera completion masks NMI and runs retained graphics
preparation. Re-enable occurs at frame7696 line10: 55,518 master clocks later.
The whole VBlank is missed. Observed NMI events are frame7694 then7696, and
camera58 is displayed for three frames before camera60. This is an actual
three-frame producer interval, not just presentation rounding.

Next experiment: avoid entering the retained graphics pass near VBlank, keep
ownership pending for interrupt-exit fallback, and test real beam timing with
a producer that consumes actual CPU cycles. A cutoff alone is not a proven
worst-case budget; route, generation/latency, audio, and negative controls remain
necessary before promotion.

## Harness improvements

- `audit_uniform_holds.py` checks all short irregular holds and revalidates
  source bindings and derived cadence measurements.
- `nes_scroll_trace.py` rejects out-of-window, malformed, unordered, or empty
  instruction evidence. Old observer737 silently ignored requested bounds;
  it is rejected, not evidence. Replacement739 uses the current observer.
- Both first-load CPU observers741 and branded CPU747 are neutral against
  complete normal timelines and PCM. Pre-camera main work in747 has no
  observed intervening ordinary NMI; the late retained graphics pass is the
  demonstrated problem, not that main-work span.
- 586 unit tests pass at this checkpoint. No hardware changes or release claim.
