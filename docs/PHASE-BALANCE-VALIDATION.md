# Phase96: recovery without the phase64 scrolling regression

Offline candidate `build/phase-balance-trial-2769/native-cpu.sfc`, SHA
`2fcd869a506a4cb0ecf26696b95009998d4753b77c8d250312869bb808b5faf9`.
Rival remains on harmonic-wub2648; no hardware input, reset or OBS change.
**One traced combat stall remains. Original-speed parity and pop-free sound
are not established.**

[Review, collages and native audio](http://127.0.0.1:8766/phase-balance-review-2805/).

## Implementation and exact-state evidence

Parent2749 was rejected for scrolling jitter. This revision changes only its
eight main-phase compare immediates64→96 and cartridge checksum. The camera
hook still permits direct publication only at/after194; the normal VBlank
publisher and all other camera writers are unchanged. No graphics, sound
engine, game counters or controller mappings change.

Oracle2771 executes50 real-beam eligibility/register/NMI cases and rejects five
mutants. Proof2776 matches every executed phase helper to all eight cartridge
banks after two verified address relocations. The unchanged camera helper is
bound to2751's86 executed cases and four rejected binary mutants. Old metadata
remains historical provenance; `experimental_phase_balance` and the top-level
phase96 value identify this revision.

Replays2773/2774 rebuild the complete128→64→camera0→96 patch chain from parent
2696 before accepting cross-ROM state. Existing controls2737/2738 reproduce all
90 frames exactly. Both initial CPU registers and full128KiB WRAM match, and
the original actual two-controller input stream is replayed.

- Event4317 is recovered: native NMI advances and the game completes on4317
  instead of4318. Pictures remain equal through4318; PCM changes from4317.
- Event2239 is **not** recovered: it still completes on2240. Cross-ROM later
  state differences remain visible rather than being called neutral.

## Scrolling and latency

Normal2770 and renderer2775 complete8874 frames with identical full timelines
and native PCM. Renderer audit2782 covers7266 eligible frames and6304 held
camera frames, with no missing lines, splits or stale-camera failures.

The important cadence check also passes: zero1/3/4-frame uniform-endpoint holds
in **both** park sweeps. East has217 two-frame and four14-frame holds; west has
144 two-frame and three14-frame holds. Long encounter stops remain included.
The parent2696 has the same histograms. The previous phase64 arms had65/28 and
81/20 short irregular holds and were not promoted.

Fresh exact-PC main/input/store/finish capture2778 and its same-core normal2777
match the independently controlled renderer run exactly. Publication audit2781
joins961 actual camera changes to all stable rendered street lines:

| Room | Changes | Main/input call→display | Store→display |
| --- | ---: | --- | --- |
|School street0|258|2 frames|1 frame|
|Alley1|129|2 frames|1 frame|
|Mall2|146|2 frames|1 frame|
|Park3|428|2 frames|1 frame|

These histograms match parent2764 with no missing displayed targets. The same
input policy is not a matched encounter or physical-button latency proof.
Room-boundary camera overwrites2406/7350 remain strict
`all_frame_end_stores_match:false` failures; neither enters a joined stable
segment. They are retained rather than converted into passing frame-end values.

## Important harness correction: a busy NMI is not a gameplay exclusion

The original game executes `STA $0107` atF189 with bit7 set while its NMI body
runs, then clears it atF1B1. The old `stable_room` summary excludes any captured
frame with bit7 set. That can exclude a real long interrupt whose busy flag
survives across a frame boundary—the exact problem under investigation.

The strict combat report always retained the failure. New
`tools/audit_busy_combat.py` adds a summary that also retains busy-NMI frames,
without changing or rewriting historical reports. All task, room, pause, fade
and transition exclusions remain individually recorded. New tests ensure a
three-frame interval cannot disappear merely because `$0107.7` is set.

Both candidate campaigns2772 complete4929 frames, with same-core observer/normal
full timeline and PCM equality, actual P0/P1 callback logs and input checks.

| Policy | Parent2696, including busy NMI | Candidate2769, including busy NMI |
| --- | --- | --- |
|Sustained attacks|1753×2 frames|1753×2 frames|
|Running/jumping|1748×2 +3×3 frames|1751×2 +1×3 frames|

Different encounters: not a percentage speedup or NES-workload equivalence.
Candidate's old stable-only summary said1749×2 with no gaps; the new summary
explicitly retains2237→2240 with busy flag set at frame2238. Strict speed
remains **FAIL**, not waived by the new categorization.

Fresh instruction window2785 is fully neutral against2784, including actual
two-port inputs. It records original NMI entry2238 line228, busy set line238,
busy clear2239 line12, and runtime return line20. The original body consumes
73,678 master clocks and crosses all of VBlank. The next main starts2240 at96.
Before that failure, the preceding main finishes2237 line162, already past the
new phase96 target. A smaller wait alone therefore cannot rescue this state.

## Menus and sound

Fresh captures2786–2789 execute19,986 frames; reviews2791–2794 pass unchanged
original-NES oracles for numeric Present Status opening/reopening, pause-menu
cursor return, two consecutive purchases and YES→NO→YES→NO/confirm NO. All
checked fixed-region pixels match; known-broken cursor/prompt controls remain
rejected. The review recomputes these oracles from authenticated source captures.

DSP capture2780 and normal2779 complete the full8874-frame route. Audit2783
verifies8432 actually received packets and1552 restarts with zero changed
configuration after restart. Raw DAC equals4,730,880 native WAV stereo frames
at32040Hz; peak6654, no clipping, damaged late-write control rejected. This does
**not** certify NES waveform fidelity, perceptual pops or physical audio.

## Additional copy-cache combination: rejected

`phase-ring-trial-2796`, SHA
`4ed31841f0827e80be8f9ad9d7a4a6add72bf4fa8d9a651cf56289df746a9295`, adds
the earlier vertical PPU stride cache to2769. Oracle2799 passes111 actual
parent/candidate comparisons,90 independent CIRAM/dirty/ABI checks and rejects
the wrong-stride mutant. Checkpoint2797 is neutral against2784; control2802 is
exact for90 frames. Replay2803 still does **not** recover2239.

Route2798 loses all power in the park, returns to room2 at9387 and times out at
10428, so full-route qualification fails. Running2P campaign2800 is observer
neutral but still has one three-frame interval2236→2239 when busy frames are
included. No audio/renderer/full-route or hardware qualification is claimed
for this combination. It remains separate from2769.

## Tests and next work

1,197 tests pass (`/tmp/rcr-tests-2806.log`). New patch tests reject every
single-byte mirror mismatch, unrelated writes and repeated application; new
busy-NMI tests prevent exclusion of the actual remaining failure.
Review2805 verifies4192 source bindings,15 published artifacts and four exact
native audio copies. The rendered page and its menu/failure collages were
visually inspected; `git diff --check` is clean.

Keep2769 as the next offline timing baseline. Shorten or safely schedule the
remaining masked original-NMI path; its late entry is driven by preceding
game work, not just the configured phase wait. Preserve all interrupt events,
PPU writes and audio updates. A replacement must recover the exact state and
repeat the actual scrolling, latency, menu and sound checks before any Rival
handoff. Physical camera holds and audible gameplay transients remain open.
