# Direct short rightward movement measurement

`movement-probe` uses the ordinary recognized-screen/idle prefix, then 24
Right frames, eight settling frames, 24 Left and eight more settling frames.
No RAM mutation, emulator speed adjustment or save-state alignment is used.
`build/movement-probe-02/{nes,snes}` retains hash-bound original RAM for
every frame, full PCM and phase screenshots.

The audited 32-frame Right/settling segment tracks the visually identified
Alex head in original OAM slots `$2F8/$2FC`. It requires tiles 1/0, attributes
`$40`, an eight-pixel separation, matching head Y at 115 or 116 (the observed
one-pixel walk bob), room 0 and camera zero. Other poses/actors are rejected
rather than followed implicitly. This is a deliberately narrow tracker,
not a general player-position RAM map.

Both runs begin at head X=39, reach X=58 by the end of the 24-frame input,
and settle at X=60: 21 pixels of total displacement. Every reference
position is reached no later by the SNES within this fixed window; most
are one frame earlier. No constant or variable time shift is fitted to the
data. `tools/check_movement.py` emits every position and first-arrival delay.
The no-slower gate passes at `build/movement-audit-01/index.html`.

Enemy states differ in the complete frames. The subsequent leftward segment
does not preserve the same actor-slot signature/combat state and is **not**
used to claim a bidirectional or combat speed pass. It remains captured.
Likewise this result does not waive the four failing loading-speed gates.

Controls reject delayed or frozen motion, reverse movement and wrong actor
signatures. The valid head test accepts only the observed one-pixel bob.
All 107 unit tests pass. Candidate remains dead-mailbox SHA
`43c6830e37399b2447640344f6c0ba329e25dcee28db1b74582574f1ec5cf0f0`.
No cartridge or hardware change.
