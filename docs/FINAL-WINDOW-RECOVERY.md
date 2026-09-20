# Shop-transition wrap fixed in3780; full-route guards pass

Cartridge `build/final-window-game-3780/native-cpu.sfc`, SHA256
`86bace9a8818ba7b4a6530e350066495aad8f46cb7f1eaf40f0cc237f8804f1f`.
Offline experiment, not deployed/default/release-ready or EverDrive-tested.

- [Real failure, corrected transition, full DMA/renderer evidence](http://127.0.0.1:8766/final-window-review-3791/)
- [Current native audio and every short-route picture change](http://127.0.0.1:8766/final-window-audio-review-3789/)
- [Remaining final-palette publication diagnostic](http://127.0.0.1:8766/final-palette-opportunities-3792/report.json)

The pages were browser-rendered and inspected. Individual before/after shop
images were also inspected. Audio clips remain untouched native PCM; no hearing
or acoustic-equivalence claim.

## Full route caught a real failure, not just a slow harness

3764 passes the two HUD cases but fails entering the shop. First fault6337 is
`vblank_overrun`; the latch stays set for2754frames, not2754 independent overruns.
Neutral full-route instruction capture3779 preserves every frame and nativePCM,
including all faults, and is explicitly a failed-game diagnostic rather than a
qualification pass. Control verification7.930s, replay26.959s, result verification7.839s.

CPU6336: the row publisher finishes259/1324; transition readiness clears state2
at the end of its scan. Final gate starts261/1314. Its latch instruction runs at
261/1350 and the following beam read sees0 after wrap. The old upper-only check
accepts0<254, starts final publication0/260, and display completion reaches line2.

3780 requires240<=latched low beam<254 after the existing hardware-VBlank and
high-beam checks. The original rejection target and transition-state rollback
are preserved. No deadline expansion, graphic change or fake completion.
The14-byte helper and guarded trampoline are the only functional changes from3764.
All256 low-beam values are tested against the emitted helper; the real old gate
is a negative that incorrectly accepts0. Three new tests and15 focused tests total pass.

At6337 the corrected game retains transition2 instead of revealing outside the
valid window;6338 finishes transition0 at254. A fresh9090-frame route has no
reported fault. Full-route original-counter and input trajectories match3764;
full RAM and pictures do not, and those differences are retained.

## Fresh qualification of3780

- Same-core DMA observer/control and separate primary-core compatibility:
  all9090 frames/nativePCM identical.52420 transfers;1920forcedblank,50496VBlank,
  4other, zero unsafe/unfinished. Latest visible completion259. Deliberate
  active-scanout, crossed-frame and unfinished-transfer mutations rejected.
- Same-core renderer observer/control:9090frames,7473eligible gameplay frames,
  6502held-camera checks, zero missing coverage, splits or stale-camera failures.
- Short-prefix audio observer finalized after process exit and neutral:
  2179packets, no clipping. Stable spacing11.312032–22.105181ms versus3695's
  9.851943–23.706695ms. Target driver gap23.617→18.778ms. Not pop-free proof.
- Prefix3781 retains the two target HUD pictures at2473/2485; counter/input
  differences from3764 are zero.89 whole-picture differences from3695 remain
  in the current audio/graphics report, including boot/setup. They are not waived.

## Do not confuse transfer safety with publication freshness

Diagnostic3792 authenticates both full DMA traces. Among8482 visible early-OAM
groups in each run,3695 has465 without a same-frame final palette batch;3780
has619. All records are retained. This does not prove a changed palette was late:
the diagnostic does not observe source generation or actualCGRAM contents.
It also cannot count as a liveness pass. Next check source/staged/actual palette
freshness at these omitted batches before accepting the graphics/audio composition.
Heavy-combat matched-NES speed, broader menus and physical/audio acceptance remain open.

## Test-cycle storage correction

3774 was explicitly terminated after confirming it was blocked in data-drive
page I/O while an unrelated Videos→data-drive rsync was active. That transfer
was not touched. It had freed122GB on the SSD, so fresh captures3775 onward were
placed in real local build directories instead of the overflow symlink.
Full9090-frame verification on SSD measured8.920s; the data-drive attempts had
spent minutes before producing a capture. This is observed contention, not an
emulator slowdown or a blanket throughput guarantee. Recheck available space
and actual I/O state before future large campaigns; preserve failed evidence.
