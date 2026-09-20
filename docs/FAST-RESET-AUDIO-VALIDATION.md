# Fast pulse-reset audio validation

Candidate `a7e363f96d71429a4b68fe77950aed5eeb5f5781c29fd23668ce0b5ab0531c7e`
uses the paired 23-byte transport and a reset-aware Memblers 2A03 SPC image.
The handler tests pulse reset bits in packet byte `$56`; reset packets combine
enabled reset voices and simultaneous duty changes into one cumulative DSP
`KON`. Normal packets jump directly to the original synthesis path. Packet
byte `$54` is safe scratch because it corresponds to NES `$4014`, which the
native CPU bridge intercepts as OAM DMA before packet storage, and boot clears
the packet page.

One unreachable trailing SPC NOP is intentional. Without it, the final upload
index has low byte `$7D`, aliasing the engine-ready token and allowing the
sender to accept the final IPL echo prematurely. Structural tests bind both
the `$4014` interception/clear invariant and this upload-token invariant.

## Executed evidence

- Pulse 1 and pulse 2 isolated tone/mute/restart/pitch probes pass.
- Reset-aware phase coherence is `.996261` / `.992272`; the old non-reset path
  is `.138226` / `.178829` in the retained controls.
- Both isolated transient audits pass against executed NES retriggers, reject
  an injected full-scale spike and reject a 1 ms dropout.
- The 7,540-frame café/mall run publishes and acknowledges 7,274 packets.
  All 32,268 CPU-side APU writes reach the checked packet state, with zero
  mismatches and zero unflushed writes.
- All 838 expected gameplay key-on packets are observed at the correct SPC
  sites. They map to 831 captured audio frames.
- Every emulator audio callback is positive and contiguous. There is no PCM
  clipping. The largest adjacent-sample step is `0.126770` of full scale;
  the executed NES reset bound is `0.171656`.

Review `build/fast-reset-opt-shop-transient-audit-72/index.html` for the full
unmodified recording, seek buttons, the 20 strongest key-on frames, waveform
plots, hashes, per-phase measurements, and negative controls. Transport and
ACK details are in `build/fast-reset-opt-shop-{bus,keyon,ack}-72.json`.

This establishes bounded digital discontinuities and lossless command
delivery for the scripted run. It is not a psychoacoustic promise, an analog
MiSTer capture, or sample-identical NES synthesis. A hardware listening pass
remains required before release.

