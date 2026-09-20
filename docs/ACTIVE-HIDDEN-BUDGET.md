# Active-loop hidden-row scheduling trial

[Combined review: collages, native audio, and remaining failure](http://127.0.0.1:8766/active-hidden-review-1998/)

Offline candidate `build/active-hidden-trial-1976`, SHA256
`9c264f313c5f27903d40560714210ef64909dfd51efd7289532570c46911f82f`.
Parent: signed-shift trial1947. **Not deployed; Rival and OBS unchanged.**

## Change and causal evidence

The preceding unconditional15-row trial failed the full-route alley fade.
Fresh-process checkpoint replay now separates immediate scheduling effects
from the different encounters caused by earlier timing changes:

- Same-ROM controls1972/1973 restore alley2426 and mall5956, then replay120
  frames each using recorded physical pad inputs. Every frame's pixels,
  original2KiB RAM, PC/P/DB, delivered inputs, and native PCM callback bytes
  exactly match uninterrupted1949. No emulated boot frames run before restore.
- Guarded constant-budget counterfactuals1974/1975 require those controls,
  exact initial128KiB WRAM, and ROM changes confined to the budget immediate
  and checksum. All output differences are retained, not scored as equality.
- From the same alley state, reducing16→15 rows moves first scenery from+8
  to+7 after rendering enable. At+3 the smaller pass lets the loop reset before
  the interrupt. It completes hidden rows later, but reaches the fade sooner.
- From the same mall state, both budgets show scenery at+6. The earlier
  full-route mall result therefore cannot be attributed solely to this cap.

New default-off `build_active_hidden_budget_trial.py` caps state2 at15 rows
**only while `$1CE1` says the camera-bearing main iteration is active**.
Inactive state2 retains16; ordinary/state1 retains2. A four-byte branch patch
at`$8864` jumps to a12-byte helper in existing unused padding at`$AA88`.
No game timer, artwork, audio engine, or interrupt handler is changed by this
new patch. The parent already includes the signed-shift and SPC dispatch work.

The selector requires native E=0, A8/X16, DB0 and decimal mode off. Its internal
V flag is not preserved; the native bridge restores caller P. Executed
oracle1979 covers1,024 transition/active-byte cases, checks X/Y/DP/SP, and rejects
a wrong-borrow ROM mutation. It does not claim interrupt-injection coverage.

## Fresh uninterrupted qualification

All ordinary route captures complete9,079 frames. DSP, main-store, and renderer
observers exactly match their respective normal timeline and native PCM.
Route lengths are not speed ratios or equal-enemy-state comparisons.

| Check | Result |
| --- | --- |
| Room-entry1978 | All3 rooms: scenery at NES+7; all40 fixed fade offsets exact |
| Whole entry latency | Room-change→visible19/27/28 versus NES20/31/30; rendering-off→visible20/28/28 versus20/31/30 |
| Cadence1985 | All3,662 stable loops take2 NMI ticks; no short irregular park camera holds |
| Renderer1986 | All7,460 eligible frames covered;6,486 held-camera frames; zero splits/stale-camera failures |
| Audio1987 |8,627 actual packets;1,601 restarts; zero late configuration writes; raw DSP DAC equals WAV |
| Audio bounds |4,840,170 native stereo samples at32,040Hz; peak6,663; zero clipped samples; damaged ordering control rejected |

The unchanged cadence audit retains10 long14-frame park holds and excluded
transitions; passing its stable-loop gate does not waive other speed failures.
Transport ordering and sample equality do **not** prove freedom from audible
nonzero pops, original-NES fidelity, or physical HDMI performance.

## Fresh menus and combat

Four new menu captures1988–1991 total20,002 frames. Unchanged oracles1992–1995
pass Status opening/reopening (RAM-derived values and fixed-region pixels),
pause cursor exit/re-entry, two consecutive purchases, and YES/NO cycling with
NO leaving money unchanged. Historical broken controls still fail. The Status
screenshot was visually inspected and contains the values.

Combat1983 has fresh normal/observed pairs for both policies,4,916 frames each.
Every same-ROM timeline and PCM comparison passes:

- Sustained attacks: all1,661 measured loops pass.
- Running/jumping:1,655 measured loops; **strict gate fails** on frames2559–2574,
  a15-frame room transition with8 NMI ticks. No exception is granted.
- This route no longer revisits the previous school-return transition. Its
  absent26-frame failure is **not** evidence that the stall was fixed.

New `review_candidate_combat.py` publishes every measured outlier with
hash-checked frame context and exact native PCM excerpts. It supports fresh
SNES-only regression without pretending a new NES/equal-work comparison was
run. Full per-policy loops, startup/other loops, and censored boundaries remain
in the machine report. Audio tests reject invalid sample bounds and mono;
the initial suite was1,008 passing, `/tmp/rcr-tests-1997.log`.

### Remaining combat load: original-game visibility context

[First alley entry from combat versus NES](http://127.0.0.1:8766/active-hidden-combat-entry-2001/)
now compares the first observed rendering-enable edge, without searching for
a more favorable later entry. The NES reference is traversal331, not the NES
combat campaign: that combat replay never leaves room0 and cannot serve as an
alley-load comparison. Input policies and actor histories differ explicitly.

Both first alley loads take13 frames with rendering off, then7 to first
scenery: **20 frames from room change to visible in each system**. All40 fixed
background/fade offsets match exactly. Thus the flagged15-frame main-loop
interval is not evidence of an added visible loading delay in this comparison.
The strict two-tick combat gate remains failed; no failure is deleted, and
neither equal CPU work nor whole-game original speed is inferred.

New `audit_combat_room_entry.py` publishes this bounded comparison separately
from cadence acceptance. Tests reject missing/truncated edges and selecting
a later entry when the first window is unsuitable. Full suite now **1,010
passing**, `/tmp/rcr-tests-2002.log`.

Fresh instruction control1999 and observed window2000 complete4,916 frames
each, with exact whole-timeline/native PCM equality, also matching the main
observer control. The window covers2556–2585 and binds the remaining loop's
exact start/end. The original `$FC73` self-wait remains unchanged; its elapsed
time must not be deducted from acceptance. These captures are available for
further attribution, not a new patch or a physical performance claim.

## Acceptance and next work

The fade regression is resolved in this uninterrupted route while sampled
scrolling, transport, and menus pass. The retained combat load now matches
original visibility, but strict cadence and physical audio acceptance remain
open. Next test school return from a controlled state and distinguish original
load behavior from true added slowdown using state-defined comparisons;
continue to qualify physical native-input audio without relying on the known
lossy OBS monitor branch. No restart or physical test was performed here.
