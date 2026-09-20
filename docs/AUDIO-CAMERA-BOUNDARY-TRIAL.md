# Camera-boundary service: measurable improvement, visual changes unresolved

Audit: http://127.0.0.1:8766/audio-camera-boundary-review-3740/

Candidate3737 SHA256:
`aad7692ad0a8b34e68a4723f277ccc58269d02b8ab7a3318f5ec1a6daf21870d`.
Parent3695 remains the last broadly scoped qualified core experiment. No default
promotion or hardware deployment.

## Exact change

Replace the replicated camera-entry STZ4200 at325C with a same-bank jump to a
helper in verified free padding7B80. The helper performs the displaced STZ,
saves full A/B/X/Y/P/DP/DB, and services a pending sound tick only with depth0,
mapper guard0, enabled shadow policy and beam60–239. It uses the existing
claim/depth-guarded real sound service, then restores state and jumps to the
verified original camera continuation325F. It does not enable interrupts in
the critical section, change audio samples, synthesize completion tokens, or
wait for a beam position. Ordinary timer/recovery remains at80.

This anticipates the observed collision where camera/retained-NMI work starts
masking at line79 and postpones the intended line80 tick until line156.

Initial3735 build failed closed because7B00 was occupied. A shell sequencing
mistake still ran3736 against the unchanged copied parent; that capture is NOT
evidence for the boundary patch. Both are retained. The actual successful build
is3737, with fresh normal3738 and process-finalized observed3739.

## Short-loop result

Both parent/trial prefixes complete2579 frames. Same-core observation is exactly
neutral independently in both arms. Trial normal replay6.606s; observed7.233s;
observed wrapper including verification and final trace authentication7.969s.

- Target frame2120 original-driver return spacing23.617→18.653ms.
- Surrounding CPU-frame1701–2399 return-gap range10.180–23.617→11.830–22.309ms.
- Actual stable sound-packet completion range9.852–23.707→11.049–22.554ms.
  Both arms retain1332 stable and846 excluded intervals; no population was
  dropped to improve the range. These are not matched-NES-workload claims.
-2179 packets and1,374,877 native stereo sample frames in each arm. Raw DAC
  equals delivered PCM exactly. No clipped samples; peak5564→5823. Neither
  count balance nor no clipping establishes pop-free or NES-equivalent sound.
- Original game-counter trajectory, logical camera and delivered inputs are
  unchanged over every prefix frame.

## Graphics tradeoff remains open

26 pictures change. Frame2408 changes744 pixels in three horizontal lines at
y186–188. Most later changes affect dialogue glyphs; two affect HUD text/health.
Every changed frame, bounding box and raw before/after picture is retained in
the rendered review, alongside untouched34–37s native audio clips. No changed
frame is silently removed or counted as an accepted improvement.

Next trace those updates through source→preparation→publication, and verify
the new helper's actual context restoration. Determine whether the sound move
delays graphics or merely shifts already-variable publication. Broader renderer,
DMA, combat and physical acceptance stay pending. This is a promising local
timing improvement, not a completed speed/audio/scrolling fix.
