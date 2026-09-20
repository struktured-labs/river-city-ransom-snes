# HUD final-batch budget audit3754

Revalidated all recorded source hashes for neutral instruction capture3749,
candidate3743 (`976c2bacbdd9950cda35d07d608709e3366bcb483bc81bcb546d0dc49dec7157`).
No fresh emulation, ROM change, promotion, or hardware restart in this audit.
Report: `build/hud-final-budget-3754/report.json`.

The proposed explanation of an unclaimed early-OAM reserve is incorrect:
earlier patches already changed row admission246→249 and final admission251→254.
Actual cartridge bytes confirm both current cutoffs. The final palette work is
unconditional, not guarded by a clean-palette fast path.

For CPU frame2472, the second row check occurs at253/276; the publisher exits
row scanning253/626 and enters the admitted final batch253/1238. That batch
executes the pending-palette preparer plus five palette DMA transfers, totaling
64bytes, before the register-update path begins255/780. Measured time from
final entry to register updates:2270master clocks. Frame2484 takes2230clocks,
entering253/794 and reaching register updates255/296. Register/HDMA setup still
remains after those points: this is not total publisher completion time.

Consequently, simply permitting the late second row while retaining final254
risks rejecting palette/display publication; raising both cutoffs would require
a new worst-case budget proof. These two gameplay observations are not that proof.
No blanket cutoff increase is justified by this audit.

Next target: reduce ready-row search delay or improve visible/mirror queue
scheduling without weakening the final-batch guard. Existing tail optimization
only saved360clocks and failed the HUD symptom, so repeating that micro-optimization
is not the next step. Keep the audio-boundary improvement experimental until its
publication regression is fixed and renderer/DMA/audio qualification is repeated.

The new audit validates executed DMA setup and immediately following instruction
boundaries. Negative tests reject missing transfers, wrong sizes, a missing final
entry and a broken DMA continuation. It does not replace general DMA or HDMA
qualification, subjective audio evaluation, or original-NES combat timing.
