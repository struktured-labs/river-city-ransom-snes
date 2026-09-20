# Local paired-SPC polling, experimental3934

ROM SHA256 `cfa07c033f0cf7211f5f5b2c28d214f562c3f384518b6ad24aae5d1f43281912`.
Parent3890, not the CPU-wait trial3919. Not promoted or deployed.

## Change

The existing receiver's empty-token path repeatedly jumps from its timer helper
back through the general receiver comparison and back to the timer helper.
A14-byte local loop at SPC3530 reads/consumes Timer0, calls the unchanged pending
timer body when needed, compares the existing token, and loops locally until
the token matches. It then jumps directly to the original receive-store code
at32E1. The main receiver's unmatched branch points to this helper.

Only the guarded dispatch operands and known zero padding at the end of the
fixed-size0x3140-byte engine change, plus SNES checksum. This padding follows the
existing interleaved-volume flush allocation. Original received-byte store PCs,
23-byte paired protocol, sound data, timer body, CPU sender, upload length and
interrupt scheduler are unchanged. It does not overlap game work with transfers
or eliminate handshake waits; it reduces some receiver polling overhead.

## Executed checks and fixture correction

Initial fixture3935 fails because its old volume-writer ownership range ends
before the current interleaved flush. Both unchanged parent and trial show
hundreds of flagged writes. This report is retained, not relabeled passing.

Corrected fixture3936 uses the already-established current-engine VolumeDriver
range through3540. Sixteen actual SPC-interpreter cases (both frame modes,
delays0/256/512/2048,101 packets then one second idle) pass timer/deadline and
writer checks. A mutant that drops consumed timer deltas fails; re-enabling a
suppressed legacy volume writer still trips the ownership check. The range was
not simply disabled. This is not an arbitrary-input byte-fidelity proof.

Synthetic packet costs are mixed: zero-delay cases unchanged; some delayed
cases slightly faster, others slower. No universal cost reduction follows.
Two separate unit tests constrain exact patch footprint/targets and reject
changed guards or occupied padding; both pass0.002s.

## Real-game narrow measurement

Normal3937 is a2,579-frame boot/right08 prefix,6.136s replay/6.285s total.
Neutral instruction3938 and parent3939 preserve every same-core primary
timeline field and native PCM;6.105s and6.202s respectively. The parent ordinary
prefix3906 is reused, not recaptured. Actual sender entryD2BC→returnD2F9:

| CPU frame | Parent master clocks | Trial master clocks |
| --- | --- | --- |
|2205|23016|21062|
|2206|23478|19082|
|2207|22672|23306|

Mean23055.33→21150; third call is slower and retained. This is not a whole-game
percentage speedup. Prefix game-counter/input/camera trajectories match; all18
changed pictures and untouched native audio appear in review3943.

## Full-route audio and remaining gates

Normal3940 and observed3941 complete9,090 frames with exact same-core full
primary timeline/nativePCM neutrality. Audit3942 retains8,641 packets,
1,588 restart checks and4,846,034 native stereo sample frames. Peak6771,
maximum adjacent step4547, zero clipping; none establishes pop-free sound.

Stable packet spacing12.226–20.858ms versus3890's12.030–20.921ms. This is a small
range improvement, not acoustic acceptance. All7,342 stable and1,298 excluded
intervals remain. Analysis27.646s separately from capture. Stable-room game-loop
populations598/1746/477/847 remain two frames each.

The full route has48 changed pictures and one changed logical-camera sample:
frame5979, enter_alley, parent0 versus trial65532. Counter/input trajectories
match. The camera difference is unresolved, not waived because it is near a
transition. Full-route visual classification, DMA/renderer, heavy2P combat,
menu/palette checks and original-NES acoustic/speed equivalence remain open.
No qualification of3890 is inherited by3934.

## Follow-up: reject promotion on text timing

Fresh renderer3948/3949 and audit3950 pass7,473 eligible frames and6,502 held
frames without splits or stale-camera failures. This does not explain away the
logical-camera sample at5979 or qualify individual tiles. Combat3946/3947 runs
both4,930-frame policies with neutral observers: sustained attacks has1,752
two-frame intervals; running jumps has1,710. No off-cadence interval or adapter
fault. The different running-jump population is retained, not represented as a
matched original-NES workload.

Text3944/3945 fails: five words are current in3890 but stale in3934. Attribution
3952 separates their causes using all frame-boundary states5985–5993:

- ALEX, row2/columns3–6: parent source5987, prepared5988, VRAM5990;
  trial source5989, prepared5990, VRAM5991. Source is two frames later;
  preparation lag remains one frame and publication lag improves2→1. These
  four late words are not evidence of a slower row consumer by themselves.
- Dialogue, row25/column12, tileE8: both source5989 and prepared5990;
  parent VRAM5991 versus trial5992. This is an actual ready-row publication
  regression, not late source or preparation.

Neutral CPU trace3951 covers5988–5991, fresh full replay22.349s. At5990 the trial
transfers mirror89 at line252/cycle1130, enters the alias25 gate at253/850, and
does not transfer that alias in the window. Parent3901 transfers visible25 at
247/840 and mirror89 at249/156. The original deadline must not be loosened to
hide this missed publication. Source phase and queue/service ordering require
separate treatment; a CPU wait already failed the earlier combat tradeoff.

New attribution tests reject censored, reordered and multiple-generation
windows and distinguish source-phase changes from ready-row delays: four pass.
Corrected review3954 retains all48 changed full-route pictures, separately adds
5979 (whose rendered pictures are identical despite the camera RAM difference),
and links the untouched native audio review. Original3952 had incorrect gallery
wording about5979; intermediate3953 failed its template guard and is retained.
These results reject promotion of3934;
3890 remains unchanged. Remaining speed/audio requirements are still open.

- [Text causes, exact CPU events, all48 picture differences](http://127.0.0.1:8766/receiver-text-deadlines-3954/)
- [Two-player combat](http://127.0.0.1:8766/receiver-local-poll-combat-review-3947/)
- [Renderer](http://127.0.0.1:8766/receiver-local-poll-renderer-review-3950/)

## Evidence

- [Actual transfer costs, all prefix pictures, native audio](http://127.0.0.1:8766/receiver-local-poll-review-3943/)
- [Full-route native audio and every packet interval](http://127.0.0.1:8766/receiver-local-poll-audio-review-3942/)
- [Executed current-engine checks and negative controls](http://127.0.0.1:8766/receiver-local-poll-current-executed-3936/report.json)

Workstation-local links. No hardware reset, MiSTer/OBS operation or release.
