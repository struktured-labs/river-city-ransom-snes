# Empty-tail scan: reproduced transition stall fixed offline

Candidate3631: `build/empty-tail-game-3631/native-cpu.sfc`, SHA256
`8a184ed9c0d24e3a70a2f99caac17f6c4aa1654f66b3dc072412cffcd546b0af`.

[Native audio, exact-frame pictures and audit](http://127.0.0.1:8766/empty-tail-review-3650/).
No default build, deployed ROM, MiSTer, OBS or controller state was changed.
The full speed/scrolling/audio goal remains active. This is not release readiness.

## Cause and change

The prior pause-audio experiment3621 remained black after loading settings.
Fresh observer3628 reproduces all2,940 captured frames and native PCM, including
the settings deadline failure. Its queue drains, but its full empty scan followed
by the transition-readiness check reaches the existing final-batch cutoff at
line254. The atomic display helper correctly refuses to reveal the screen and
restores pending state2. The same rejection repeats after the work is finished.

`snes/consumer_empty_tail.asm` retains the existing eight-entry mixed/empty scan
but consumes scalar misses locally instead of re-entering via the original row
consumer. Byte-wide tail reads cannot spill past flag127 into CHR flags. Ready
entries still enter the verified original instruction at83D7. Cursor, budget,
row order, producer, all graphics, sound engine and DMA deadlines are unchanged.

Applying only this scanner to rejected3621 produces diagnostic3629. Its complete
2,536-frame pause/status replay and neutral observer3642 recover settings. At
frame580 the old and new scans enter at exactly the same clock with the same
A/X/Y/S. The scan decreases8,980→8,698 master clocks. Final admission moves
line254→253 and the actual display path executes. Frame582 changes from black
to settings. This proves the reproduced failure, not every possible arrival phase.

The isolated candidate3631 applies that same scan change to working3583, without
the earlier pause-audio move. The audio move was not retained: both versions
still fail the original pause onset gate,58 versus57. Its observer3637 shows
prepublication sound executing, but some calls still span the frame boundary;
there is no demonstrated pause-onset benefit.

## Qualification of isolated3631

- Exact-state health3638 and dialogue3639 preserve initial fullCPU/WRAM/VRAM,
  inputs, original-game counters, cameras, sprite source/staging and playfield
  pixels. Health remains3frames; all11 dialogue updates remain2–3frames. Full
  cross-cartridge RAM/register/PCM differences are retained, not declared equal.
- Ordinary pause/status3632 completes2,536frames. Status opening/reopening digits
  and checked pixels match NES. Pause sound gate3635 remains FAIL.
- Full route3640 completes9,089frames. Actual renderer3644/audit3646 covers7,475
  eligible frames, with zero missing-coverage, split or stale-camera failures.
  Its same-core unobserved3641 matches full execution and native PCM exactly.
- General DMA3647/audit3648:53,455 transfer envelopes, zero unsafe envelopes;
  latest visible end line259. Includes1,897 forced-blank,51,554 VBlank and4 other
  transfers. Core-build control3645 and same-core observed execution match.
  HDMA/per-byte physical timing is outside that observer.
- Neutral audio3643:8,641 commands,1,585 checked restarts, startup gate passes.
  Native32040Hz stereo:4,845,501 samples, peak6,592, maximum adjacent step4,577,
  no clipping. These numbers do not certify absence of popping or acoustic
  fidelity; no subjective hearing claim. Stable-route cadence has3,667 measured
  two-frame intervals. It is not a matched-original-NES workload proof.
- The inherited exhaustive queue oracle passes all four new tests. Full suite:
  1,428 tests in24.240s (`/tmp/rcr-tests-3649.log`). DMA unsafe-scanout,
  crossed-frame and unfinished-transfer controls reject. The actual failed
  cartridge remains a negative control rather than being overwritten.

Short authenticated probes took6.43–6.49s; neutral transition capture6.278s.
Review3650 generation and source validation took55.915s. The page exports only
reviewed PNG/WAV/JSON/HTML, never ROMs or save states.

## Remaining work

The graphics/audio interaction is now understood for this stall, but the one-frame
pause onset and physical popping remain unresolved. Investigate original-NES
cue/driver/callback phase before another scheduling move. Recheck exact sprite
and CHR publication, broader menus/controllers and original-NES matched speed
on the eventual candidate, then qualified physical capture. None of the broader
goal requirements is waived by this local fix.
