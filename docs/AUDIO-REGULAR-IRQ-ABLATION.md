# Camera pre-service ablation4033 — rejected, next safe point identified

Exact ROM `83339328e5b5d10847ca76775de80f2b34b3a0e2c8427956e9eb6e0b0452ff24`.
Parent3955 remains unchanged. No default ROM, hardware or release promotion.

## Change and qualification

At7BE3 in each of eight runtime banks, replace the first three bytes of the
camera pre-service guard with JMP325F. Retain STZ4200, the existing late-NMI-edge
wait7E00, normal line80 IRQ, pending ownership and recovery. SPC and graphics
bytes are unchanged. Four patch/event-analysis tests pass0.118s, including all
160 guarded-byte mutations, repeat-patch rejection, exact changed-byte extent,
missing/censored invocations and nonmonotonic trace rejection.

Initial builder attempts failed closed: first the camera-entry guard exposed
the retained edge-wait trampoline; then a guard-length typo was corrected.
Failed capture directory4034 is retained; it contains no completed replay.
Successful ordinary4035 and observed4036 complete9,090 frames with exact
same-core primary timeline/native PCM neutrality. Report4037 keeps all8,641
packets,1,588 restarts and4,846,034 native stereo sample frames. No clipping.

| Stable packet gap |3955|4033|
|---|---:|---:|
|Minimum ms|12.147901|9.861696|
|Maximum ms|20.857717|23.883232|

All7,342 stable and1,298 excluded intervals remain. Four room populations
598/1746/477/847 retain two-frame cadence. Route game-NMI/outer-NMI/input/fault
trajectories match, but23 pictures,7,876 game-RAM samples and one camera sample
change. Every changed picture is retained. These results do not establish
original-NES speed or acoustic acceptance. Audio analysis took28.300s.

## Local hypothesis confirmed, global ablation rejected

Authenticated reused3955 CPU trace4003 versus fresh neutral4038 shows frame8531:
camera continuation moves from71/64 to34/810; interrupt policy restores at71/406
instead of106/1206. Sound begins at80/1070 instead of37/312. In this case the
early sound call itself had pushed camera work past the regular deadline.
4038 replay25.485s; this is measured execution, not only a counterfactual.

The worst full-route gap nevertheless worsens. Fresh neutral4040 traces2119–2121
(22.351s replay), separately revalidated against its same-core control:

- CPU frame2120 camera entry78/188, continuation325F at78/708.
- Camera publication completes: next instruction3262 at78/1020.
- JSR7F00 preparation starts3265 at78/1046 and returns3268 at100/1038:
  30,000 elapsed master clocks.
- Retained original game NMI is pending; its entry JML[1C00] executes at3282
  (full PC C73282) at100/1310, after depth is incremented.
- Sound service7885 is not entered until156/272; original sound driver starts
 156/880 and returns198/676. Final policy store33A6 occurs217/174.

The packet audit's sample-derived frame interval2119→2121 and CPU frame2120
are different clock-domain observations; do not equate those labels silently.

## Next mechanism

Investigate a guarded sound-recovery call **after preparation returns at3268,
before entering retained original game NMI**. This location avoids spending
the early interval in a busy wait and offers a service opportunity before the
long retained handler. Use existing pending/depth/mapper/beam guards; do not
fake a completed token, bypass the original sound busy flag, or enable hardware
interrupts in unfinished work. Verify actual register/stack preservation and
both identified windows before broader text/combat qualification. No such
recovery patch is implemented or declared safe by this report.

- [Audio failure and all23 changed pictures](http://127.0.0.1:8766/audio-regular-irq-review-4039/)
- [Untouched native audio and every packet interval](http://127.0.0.1:8766/audio-regular-irq-audio-review-4037/)
- [Audio issue6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6)

Review4039 rendered and visually inspected. No physical-console audio claim.
