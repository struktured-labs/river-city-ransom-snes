# Sprite attribute lookup

`build/sprite-table-01` replaces per-sprite bit reconstruction with a fixed
256-byte mapping and computes the sprite pattern-half bit once per snapshot.
No artwork, sprite order, coordinates, priority or palette choice is intended
to change. The input is explicitly masked to 8 bits before the 16-bit index
transfer, so a stale accumulator high byte cannot select outside the table.

`tools/check_sprites.py` compiles the production producer in an asset-free
fixture. Eight runs cover all 256 attribute bytes in both pattern halves;
each compares all 256 staged OAM bytes against an independent Python oracle.
Coordinates include off-screen Y values. Corrupting lookup entry 0 or 255
must fail the executed OAM comparison. `build/sprite-table-oracle-02` passes
both the positive runs and these two negative controls. The existing graphics
suite and 86 unit tests also pass.

The full baseline completes in 2098 frames versus 2099 before the lookup.
In the 12000-frame walking profile, measured after frame 1800, two-frame NMI
intervals decrease from 42 to 24, and the maximum interval from 31 to 30.
These runs use the same host input schedule but can diverge in encounters;
they are not a controlled same-state proof of an 18-frame gameplay gain.
Long loading stalls remain, and original-speed transition gates still fail.

Audit: `build/sprite-table-quality-01/site/index.html`.
This staged-OAM test is not proof that the user's corrupted mall NPC scene
is repaired, nor does frame pacing establish audio fidelity. Not deployed.
