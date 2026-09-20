# Current cartridge: sustained combat regression

September 18, 2026. No cartridge changes or hardware inputs in this iteration.
Tested cartridge SHA256:
`0e9ba29becef5dc548a81d016d0e0311731244a3fc2cc8292db321c9dd2ac12d`.

[Audit page: screenshots, native audio, every timing outlier](http://127.0.0.1:8766/combat-outlier-review-1817/).

## New coverage

`tools/combat_campaign.py` adds two input-only encounters without modifying
historical benchmark policies or injecting game RAM: 24 seconds of repeated
kicks followed by 24 seconds of punches, and repeated right/jump followed by
left/jump. Both retain approach and pause/resume requests. Phase names inherited
from the earlier test describe input requests, not proven knockdowns or pauses.

Eight fresh processes cover two policies, two systems and observer on/off.
Each pair uses the same core binary. All 38,092 captured frames are retained;
each traced run exactly matches its independent untraced run's complete
timeline and PCM. Capture receipts bind the policy implementation, ROM, core,
observer sources, exact-PC trace, images and audio. The verifier also checks
every full-RAM row against its original frame hash.

The earlier short combat scenario was rerun separately on this cartridge:
1810/1812 and audit1813. All 701 measured SNES iterations and the existing
original-NES reference's 701 iterations retain two ticks and two-frame starts.

## Results, including failures

| Policy | System | Complete measured loops | Strict all-two-frame gate |
| --- | --- | ---: | --- |
| Sustained attacks | NES | 1,660 | FAIL: one three-tick/three-frame loop |
| Sustained attacks | SNES | 1,661 | PASS |
| Running/jumping | NES | 1,648 | FAIL: three three-tick loops; one 25-frame interval |
| Running/jumping | SNES | 1,642 | FAIL: 15- and 27-frame intervals |

Original-NES three-tick events start at frame1504 in sustained attacks and
1556,2075,2750 in running/jumping. These stay in room0, gameplay task `$C0`,
unpaused, original mode4. This demonstrates occasional longer original loops
in these emulated encounters—not that the user's hardware slowdown is normal.

The original's frame3119..3144 interval is particularly important: its observed
game tick counter reads **two**, while **25 emulator frames** elapse. Its room
ID remains0; the task/mode changes and the picture fades to black. It is not
asserted to be a room-ID change or paired with either SNES transition. This
is why the harness checks real frame spacing independently of tick counters.

The SNES frame2560..2575 loop crosses room0→1 and native transition states1/2,
with eight observed NMI advances. Frame4177..4204 crosses room1→0, with seven.
They remain failed observations, with full frame-state lists, exact images
and native audio excerpts; the transition annotation never waives a failure.
Other measured SNES loops have two ticks and two-frame start spacing.

The different routes and enemy encounters prevent an equal-work speed ratio.
Neither this test nor the earlier short pass certifies the park encounter,
whole-game original speed, MiSTer timing, or pop-free sound.

## Audit controls and reproduction

The existing cadence auditor rejects derived mutations for a third tick,
extra physical frame and missing loop in every system/policy. New unit tests
cover isolated/restored policy dispatch, unsupported cores, longer policy
coverage, a 25-frame interval hidden behind two ticks, inter-loop gaps,
phase boundaries, transition annotations and exact audio callback boundaries.
The full suite passes **977 tests**.

Each capture is a fresh process; for example:

```sh
python3 -m tools.combat_campaign capture --system snes \
  --core .deps/snes9x/libretro/rcr_main_store_libretro.so \
  --candidate build/word-pitch-1699/game --policy running-jumps \
  --out build/NEW-CAMPAIGN/running-jumps-snes-normal
python3 -m tools.combat_campaign capture --system snes \
  --core .deps/snes9x/libretro/rcr_main_store_libretro.so \
  --candidate build/word-pitch-1699/game --policy running-jumps --observed \
  --out build/NEW-CAMPAIGN/running-jumps-snes-observed
```

Repeat both policies for NES using
`.deps/fceumm-raster/rcr_raster_libretro.so` and `--system nes`; the candidate
argument still identifies the SNES build under comparison. Then:

```sh
python3 -m tools.build_combat_outlier_review \
  --root build/NEW-CAMPAIGN --candidate build/word-pitch-1699/game \
  --out build/NEW-REVIEW
python3 -m unittest discover -s tests -q
```

Capture1811 initially selected a NES core without the required trace observer;
the traced NES runs failed, not passed. The tool now rejects that core before
capture, and all eight authoritative runs were repeated in1814. No failed
artifacts were deleted. Review1815 contains the campaign;1816 initially selected
only non-two-tick examples and omitted the original's25-frame/two-tick event.
**1817 supersedes both reviews**, selecting tick and physical-span outliers.
That omission is now covered by a specific unit test.

Rival and OBS were untouched. Remaining work is the rare hardware slowdown and
SPC/acoustic discontinuities, using the new direct-input PCM reference rather
than trusting the monitor branch. This iteration expands regression coverage;
it does not claim a new gameplay or audio fix.
