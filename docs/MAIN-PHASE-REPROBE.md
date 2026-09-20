# Earlier main-loop reprobe: one recovery, scrolling rejection

Both candidates remain **offline and rejected for scrolling cadence**. Rival
is unchanged on harmonic-wub2648. No MiSTer input, reset, OBS routing or
recording change was made in this goal turn.

Review with actual rendered-camera collages and native same-state audio:
<http://127.0.0.1:8766/main-phase-review-2768/>.

## Changes and executed helper checks

Parent is masked-budget2696, phase128. This experiment does not include the
ring-stride2715 optimization, whose full route was incomplete.

- `main-phase64-trial-2734`: changes only eight128→64 main-wait compare
  immediates and checksum. SHA
  `06656572c7cf4e7128072bd18a8e59de292b8125f79939c2d70e522e4782b839`.
  Existing eligibility, interrupt policy, register preservation and high-beam
  no-wrap behavior remain. Oracle2735 executes50 cases and rejects five
  damaged controls. Patch proof2744 binds **every** executed helper to all
  eight production banks after exactly two address relocations.
- `phase-camera-trial-2749`: builds on2734 and changes only eight early-camera
  admission compares30→0 and checksum. Direct camera-tail publication is now
  allowed only at/after194; other publishers remain unchanged. SHA
  `9430a2127dce4484cb92b8e6cc2e2d031d0b84686b13dad5213e92aff544e103`.
  Oracle2751 executes the actual51-byte production helper in86 real-beam
  cases and rejects four binary mutants. No assembly approximation, added
  wait, alternate audio engine or new graphics producer is used.

## Same-state evidence

Both arms use neutral checkpoints from the exact instruction-core parent
run2707, actual two-port inputs and passing90-frame same-ROM controls2737/38.
Cross-ROM replay rebuilds the entire allowed patch and requires complete
128KiB initial WRAM and CPU-register equality. It rejects checkpoints inside
either changed helper.

| Known missed edge | Phase64 | Phase64 + camera cutoff |
| --- | --- | --- |
|2239, restore2234|Still missed; completion2240|Still missed; completion2240|
|4317, restore4314|NMI and completion recovered on4317|Same recovery|

For the recovered case the parent completes on4318; pictures remain identical
through4318. PCM changes from4317, as expected when game/sound scheduling changes.
Later cross-ROM state differences remain recorded; these are not claimed to
be neutral replays or matched later enemy workloads.

The independent two-player campaigns2742/2757 each complete4929 frames, with
normal/observer full timeline, PCM and both input ports matching. Both arms
have1753 stable two-frame sustained-attack intervals; running/jumping has1749
two-frame intervals and **one three-frame interval2249–2252**. That remaining
interval contains three native NMIs, not a missing native interrupt. It is
still a strict speed failure. Parent had three gaps; independent encounter
counts are not equal-work speed ratios.

## Why neither candidate is deployable

Both full park routes complete8874 frames. Full renderer controls are neutral;
audits2745/2758 find no missing lines, splits or stale-camera failures. Those
checks alone would miss the important regression:

| Arm | East short irregular holds | West short irregular holds | East/west1–3 pairs |
| --- | --- | --- | --- |
|Parent2696|0|0|0 / 0|
|Phase64|65|28|23 / 11|
|Phase64 + cutoff0|81|20|28 / 6|

All matching-two-pixel endpoint holds are retained, including long encounter
stops. Short irregular means1,3 or4 frames, not just adjacent1/3 pairs.

Fresh exact-PC main/input/store/finish captures2754/2756 and same-core controls
2753/2755 also match their independently controlled renderer runs exactly.
Reports2763/2764 join actual stores to all stable rendered street scanlines
without fitting frame lag. Each arm has961 covered camera changes and no
missing displayed target. Parent main-start→display is two frames for every
covered change. The camera-cutoff trial is:

| Room | One-frame main-start→display | Two-frame main-start→display |
| --- | --- | --- |
|School street0|5|253|
|Alley1|0|129|
|Mall2|146|0|
|Park3|149|279|

Store→display is one frame throughout both joined samples. The variation
starts **before the camera commit**, not merely at the early direct-copy
threshold. For example the trial's main starts7616/7618 at line64 and commits
in those same frames at line239; start7620 commits at7621 line38. Parent starts
7616/7618/7620 at128 and commits next frame at92/98/103. Thus some early-start
camera computations beat the first VBlank, while others cross it. Merely
removing the before-line30 publication opportunity does not make the cadence
uniform.

Initial latency-check attempts correctly stopped on camera stores overwritten
later in the frame at room boundaries. Final reports retain these as strict
`all_frame_end_stores_match:false` failures: parent7350; trial2406/5933.
None may enter a joined stable segment. They are not silently converted to
frame-end camera values or counted as passing stable latency events.

## Audio and tests

DSP runs2747/2760, independent same-core normals2746/2759 and audits2748/2765
each verify8431 actually received packets and1549 restarts, with no changed
configuration written after restart. Raw DAC equals4,730,880 native WAV stereo
frames at32040Hz; peaks6362/6295, no clipping. Late-write analysis mutants are
rejected. This is transport/ordering evidence, **not a pop-free or NES-fidelity
certificate**. Splash sound is unchanged.

Full suite:1193 tests pass (`/tmp/rcr-tests-2766.log`). New tests reject
unrelated/checksum-hidden edits, every changed camera-preimage byte across
all eight banks, mismatching mirrors, incomplete/non-neutral observers and
lost frame-end overwrite evidence. Existing exact-store joins retain their
delay/missing-display regression coverage.

Review2768 verifies1530 source bindings,13 published artifacts and four exact
audio copies. Its rendered page and collages were visually inspected.

## Next experiment

Do not promote either arm or hide the jitter by globally adding a frame.
The earlier96-line schedule plus the independently verified camera cutoff is
a bounded next candidate: it may keep camera work after the first VBlank while
still giving late retained interrupts more room than128. That is a hypothesis,
not a measured fix. If it still crosses boundaries, stage camera generations
against the game's two-tick update schedule and cover **all** publisher sites,
including late-NMI and final-register copies. Recheck exact-state recovery,
actual input/store-to-render timing, all room transitions, menus, complete audio
and physical scrolling before any Rival handoff. The remaining three-NMI combat
interval also needs its own instruction-cost diagnosis.
