# Audio/HUD composition: targeted recovery3764

Candidate `build/overflow-3526/postrow-stop-game-3764/native-cpu.sfc`, SHA256
`8ed9aafe6af975023bfd7fd24a9ca0419a6b82db7916099dc6ef2c31f902cc29`.
Experimental, not promoted or deployed. Neither MiSTer was touched.

- [HUD screenshots and exact failing controls](http://127.0.0.1:8766/hud-recovery-gallery-3773/)
- [All86 changed pictures and untouched native audio](http://127.0.0.1:8766/postrow-audio-review-3772/)
- [Source-bound HUD gate](http://127.0.0.1:8766/hud-recovery-3770/report.json)

Both web pages were rendered and visually inspected; the native WAV serves200.
No waveform/listening equivalence or pop-free claim.

## Three causal experiments

3755 adds bounded suffix unrolling to3743. It preserves exact queue order and
visit budget, with the mixed-group scanner for partial suffixes. Four emitted-code
oracle tests exhaust all cursors/budgets and single-ready positions plus1500
random queues and the historical wrong-continuation negative. Size1084bytes;
extension verified unused. It boots successfully but HUD updates are still late.
Second-ready check2472 improves253/276→251/292;2484 improves252/1196→250/1276.

3760 then changes row cutoff249→252 with final254 unchanged. Both target HUD rows
arrive next frame, but continued empty scanning reaches finish at254/916 and
254/922. The final palette batch does NOT execute in those frames. Rejected.

3764 adds a15-byte post-transfer helper: call the existing row admission check
before searching more entries; if late, save the next cursor and exit to the
unchanged final gate. Skipped ready entries remain owned/ready; no fabricated
completion, new priority, persistent queue or graphics modifications.

Now both original/staged HUD generations match the parent and both actual64-byte
VRAM rows and whole pictures match3695 at2473 and2485. All five final palette
DMAs also execute in both CPU frames2472/2484. Final entry2472 is254/28 because
the existing beam latch admitted it on253; register updates start255/934.
The gate is unchanged, not bypassed. Full transfer safety remains separately
required. The combined symptom/tradeoff audit rejects both real failed variants.

## Preserved checks and limits

All2579 prefix frames retain original counter, camera and delivered-input
trajectories. State and instruction observers are independently neutral against
the same exact core/ROM control, including every primary frame and native PCM.
Twelve focused unit tests pass.86 picture differences from3695 remain visible,
including boot/setup differences; the two-event pass does not waive them.

2179 audio packets / native PCM are observed with finalized trace hashes.
Stable sound-packet spacing3695:9.851943–23.706695ms;
3764:11.190114–22.158825ms. Target driver gap23.617→18.682ms.
No clipping. These measurements do not establish acoustic fidelity/pop-free sound.

New normal prefix replay10.272s; neutral state8.738s; instruction9.061s; audio9.090s
(16.070s including authentication/finalization). Some runs overlapped; no claim
that concurrency reduced latency. Parent source verification on the data disk
can now dominate wall time. Full ordinary route3769 completes9090frames.

The first full DMA-control attempt3771 terminated with exit143 during reference
verification, before creating a capture directory or valid receipt. It is not a
test verdict. After confirming the process was terminal and no capture existed,
a fresh retry3774 was started. Full DMA/renderer, final-publication liveness on
other scenes, menus, combat speed and physical SNES/EverDrive acceptance remain
open. Do not inherit3695's broad qualification onto3764.
