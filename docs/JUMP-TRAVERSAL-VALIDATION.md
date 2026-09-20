# Input-only jump traversal

`traversal-jump` preserves the recognized street prefix, holds Right, and
pulses logical NES A+B for four frames every 30 frames. The new optional
`hold_buttons` phase field retains Right during pulse-off frames; the capture
verifier independently checks that exact schedule. No save-state injection,
RAM mutation, collision bypass, frame skipping or emulator speed override is
used. `traversal-jump-lower` adds 90 Down frames and 18 further 120-frame
right/jump phases. Unit coverage checks unchanged prefixes and added inputs.

`build/jump-route-01/{nes,snes}` completes in 5512/5650 display frames.
`build/lower-jump-route-01/{nes,snes}` completes in 7762/7900. These are total
script durations with different encounter states, not a same-state gameplay
speed comparison. Captures retain per-frame audio/register/input/RAM hashes
and phase-end screenshots, not every-frame PNGs for these exploratory runs.

Both versions reach the trash-pickup area. At `right_35` and
`lower_right_17`, the original game camera and scroll registers both equal
255 in both versions. The explicit camera audit compares the same fixed
background strip `(0,32)-(256,112)` without actor masking or image alignment.
The first pair has 74 differing pixels; the lower-lane pair has zero out of
20480. Complete images show different player/enemy states and remain visible
in the audit. This is scoped background evidence, not full-scene equality.

Web collage: `build/lower-jump-route-01/camera-audit/index.html`.

Both routes remain in this area rather than reaching the mall. The right-edge
stop is therefore not established as a SNES-only scrolling fault. Additional
route/encounter handling is needed to reproduce the user's mall and shop
reports. Do not replace that requirement with these passing strip pixels.
Nothing deployed to Rivalmage.

Follow-up: the added `traversal-mall` route goes up through the alley and
does reach the mall. It exposes a missed mapper-write patch and verifies its
correction; see [mall mapper validation](MALL-MAPPER-VALIDATION.md). The older
right-only routes above are retained as evidence, not the final route.
