# Fused sound-register commit: fixed rendered scrolling sample

Experimental candidate `build/sound-commit-on-418/native-cpu.sfc`, SHA-256
`711681c49ca025d776bd546026328498dd9ddb7b5c2836ab830f8f132f5c4168`,
is **not deployed**. It fixes the previously proven park scroll split, but
first-room loading, strict publication/settling gates, broader combat speed
and physical gameplay sound still prevent promotion or a Rival restart.

## Implementation and executed oracle

Default-off `experimental_sound_commit` replaces the pinned original bank-5
`$8735` entry with `native_sound_commit`. The helper still writes `$07D6,Y`,
suppresses stolen music channels using `$074C,X`, maps SFX channels through
`Y & 15`, and preserves the dynamic pointer and original return behavior.
Channel/enable writes update the same APU shadow, timer flags and length gate.
Other addresses retain the generic dispatcher. Fast writes omit unused private
diagnostic mailbox updates; this is not a byte-identical whole-WRAM claim.

The helper saves X and the original result A once. Its body does not change
V/D/I; final `CPX #4` and `PLA` reconstruct precisely the original C/N/Z.
A remains on the stack across interrupt re-enable, not reloaded from mutable
sound RAM afterward. Zero-flag registers skip redundant flag writes, and the
interrupt-depth check short-circuits before reading the second ownership guard.
The direct-APU prerequisite also prohibits the unqualified raster scheduler.
Graphics, game timers, music data and the SPC engine are unchanged.

`sound-commit-off-424` is byte-identical to parent candidate 405:
`7b52e63d0e6f62d2656303baababdbe96f34b376c9dd13e141b9f0f177ae0fb1`.
New build manifests explicitly hash the direct-APU, bank-restore and fused
sound include files; old manifests have not been rewritten.

`sound-commit-oracle-420` passes **98,496 executed cases**:

- 98,304 paired original-versus-fused calls: X=0..7, Y=0..31, every input byte,
  varied status/enable/length/flags, active and suppressed music channels.
  Independent CPU/APU state checks plus final source-shadow/pointer checks.
- 192 fresh masked hardware-NMI cases, with all four ownership combinations.
  Exactly one service is required only for unmuted writes with both guards
  clear. A synthetic handler deliberately changes the source sound RAM;
  return A must still be the saved original value.
- Nine rejected mutants: wrong SFX mask, lost music suppression, wrong shadow,
  disabled length reload, lost enable clear, lost flags, acknowledged-away
  pending edge, ignored interrupt ownership, and post-NMI source reread.

These fixtures use E=1, nonzero DP and mirrored DB. Source/pointer aliases for
Y>=32 and mapper-address fallbacks are not covered. Generic DMA/controller
fallbacks execute in the matrix, but their non-APU effects are not independently
modeled. Pending-edge cases cover accelerated/muted paths, not the full game
NMI body or physical hardware.

`sound-commit-timing-424`: 192 matched calls, full observer WRAM equality.
Channel writes save **436–616 master clocks**, enable writes 476–516, and
tested fallbacks 214–294. Muted-path differences range from -34 to +46 clocks;
elapsed samples include refresh/events. No full-game speed ratio is implied.
448 Python tests pass; `git diff --check` is clean.

## Gameplay and exact renderer proof

`sound-commit-render-regression-424` reuses the **same** NES frame 7604 and
SNES frame 8670, room 3/camera 240. It refuses frame rematching. The prior ROM
drew scroll 242 on lines 32–158 and 240 on lines 159–191. The new ROM draws
**240 on every line 32–191**, matching NES. Both background pixel bands now
have zero differences. The camera hook moves from line 38/cycle 528 to
**line 30/cycle 954**. The before/NES/after images are unchanged captures.

`sound-commit-camera-audit-420` measures sound-driver elapsed time in this
exact interval at **32,084 clocks**, down from 41,482 in parent 405. The total
camera-hook improvement is 10,486 clocks; other stage timing changes as well,
so do not attribute every saved clock exclusively to the helper.

The renderer, background and CPU observers each retain the full normal-core
8,807-frame timeline and PCM. Renderer traces now flush and bind their hash
inside the fresh capture process (`render_scroll_trace`); the new regression
checker requires that binding. Earlier observation 422 predates this additional
binding and is superseded by 424, not retroactively rewritten.

| Evidence under `build/` | Result |
| --- | --- |
| `sound-commit-background-audit-420` | **Overall FAIL retained**. All 742 common background positions match, coverage 259/113/105/265. Both routes complete; all observers neutral; known broken control detected. Publication and settling gates still fail. |
| `sound-commit-entry-420` | First scenery 8/7/7 vs NES 7/7/7. Whole loads 24/30/29 vs 20/31/30. Only room-1 fade offset 7 differs; rooms 2/3 match all 40 checkpoints. |
| `sound-commit-park-audit-420` | No native faults or stable unpaused park packet interval over 1.5 frames. |
| `sound-commit-audio-420` | All 9,223 completed-NMI packets verified, no unfinished tail or unflushed writes; full PCM and gap clips retained. **Not a pop-free verdict.** |
| `sound-commit-neutral-spans-422` | All 9,408 fixed-route rows and PCM identical to normal core; no late NMI-entry interval in observed window. |
| `sound-commit-status-audit-422` | Both Present Status entries match NES exactly, including numeric values. |

The remaining frame-end publication warning is frame 7901, camera 379 versus
table 377. `sound-commit-edge-423` places the hook at line 239/cycle 1266,
crossing the NMI edge. `sound-commit-raster-423.csv` draws 377 across frame
7901 and 379 across frame 7902; this is not the repaired mid-frame split.
The gate remains failed. Settling failures also remain unrelaxed; many arise
because the first consecutive sample occurs only on the return traversal and
are not claimed to be literal thousand-frame rendering stalls.

The initial implementation 414 passed its helper oracle but still reached the
camera hook at line 33. Its failed whole-game evidence is retained. Candidate
418 is the refined implementation described here, not a relabeling of 414.
