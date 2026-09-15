# Left-edge BG and sprite clipping

The initial street uses PPUMASK $18: rendering is enabled, but the first eight
pixels of each background/sprite scanline are hidden. The port previously used
only the layer-enable bits. It now maps the two left-edge controls independently
to SNES window 1, fixed at x=0..7. The window settings are updated during the
bounded publication step, not during visible scanout.

Register definitions were checked against the pvsneslib project's
[background/window register declarations](https://github.com/alekmaul/pvsneslib/blob/master/pvsneslib/include/snes/background.h).
No original graphics assets are changed.

## Executed tests

`tools/check_video.py` tests masks $18/$1A/$1C/$1E, with the fixture initially
using the opposite left-edge controls before switching them live. It compares
every output pixel against an independent image oracle. A sprite at x=4
straddles the boundary: x=7 can be hidden while x=8 must remain visible.
Widening the window to nine pixels deliberately fails the oracle. Existing
scroll-split, late-entry, cache, row-drain, and CHR controls still pass, as do
59 unit tests.

Candidate `build/left-clip-01/native-cpu.sfc`, SHA
`74fe0decfe571e9f43897ffd54aa914db4ee50e1f7947d3b9e0591f3e53326dc`,
still completes the baseline in 2,035 frames. In the initial idle street view,
the fixed upper-background rectangle x=0..255, y=32..111 now matches NES at
five-bit RGB precision: 0 mismatching pixels, versus 545 before the change.
The benchmark now enforces this strip through `initial_street_background_pixels`.
Re-evaluating the old capture fails that new gate; the new capture passes it.

The updated audit is `build/left-clip-quality-01/site-with-edge-gate/index.html`;
the old-candidate control is `build/left-clip-quality-01/before-edge-gate/index.html`.
Settings pixels still pass. All four transition speed gates still fail. The
12,000-frame walk retains a maximum NMI interval of 23 frames and detects no
VBlank overrun. This does not certify full scrolling, actor rendering, audio
fidelity, or original speed. Rival was not changed.
