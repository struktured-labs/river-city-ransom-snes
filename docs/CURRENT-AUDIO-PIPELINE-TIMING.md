# Current audio: arrival timing versus SPC service

Candidate3032 remains unchanged:
`a38458515709e0048b5d5b6e5e6ca58888cd3151ea7d839741468f6c106398ba`.
Neither MiSTer, OBS, controllers nor saved settings were accessed. Rivalmage
remains off-limits; Bluemage is permitted for subsequent qualified testing.

[Timing evidence](http://127.0.0.1:8766/final-batch-audio-timing-3061/)
revalidates the existing9,248-frame DSP capture3039 against neutral route3035,
actual received bytes, CPU packet writes and exact raw-DAC/WAV samples. This
is a new analysis, not a new cartridge or hardware capture.

## Result

8,802 packets have complete ordered receipt/ready pairs. For7,609 consecutive
gameplay intervals with no transition-state flag:

| Timing population | Minimum ms | Median ms | p99 ms | Maximum ms |
| --- | ---: | ---: | ---: | ---: |
| Last-byte receipt interval |11.9314|16.6081|19.2962|21.1454|
| Ready interval |11.7548|16.5496|19.4005|21.1454|
| Change in post-receipt service duration |−0.6788|0|0.4886|0.8427|
| Post-receipt service duration |0.8066|1.1548|1.5137|1.8336|

Milliseconds use the native nominal32,040Hz DAC rate and32 SPC clocks/sample.
Service population includes the7,614 distinct packet endpoints of the retained
intervals. Across all8,802 packets, including nongameplay, service can be as
short as478 clocks; that is not the gameplay minimum in this table.

Each interval satisfies exactly:

`ready gap = receipt gap + current service duration − previous service duration`.

Most of the observed completion-cadence variation is already present at
last-byte receipt. The longest completion gap,21.1454ms at packet2342, has
zero change in service duration. This directs investigation toward the
original-driver/publication/transfer path before changing SPC synthesis
scheduling. It does **not** establish which upstream stage causes the
variation, whether the variation is audible, or whether it differs from the
original NES under equal game work.

## Clock and event safeguards

The observer emits receipt and ready records before the final write tick.
`validate_trace` already adds one tick to receipt; this analysis also adds
one tick to ready. This constant does not alter consecutive ready intervals.
DSP register-write timestamps are already completed ticks. Callback contexts
are derived from DAC samples, not equated to `IPPU.TotalEmulatedFrames`.

The same12 frozen waveform edges from review3058 retain exact sample/channel,
nearest preceding receipt, readiness offset, last DSP write and raw CPU shadow
and port-write coordinates. Negative readiness offsets are kept: some edges
occur during register setup before software ready. Proximity alone is not
causation; these remain listening candidates, not proven defects.

CPU beam coordinates are preserved without converting them into a fabricated
shared CPU/SPC epoch. Receipt is the final packet byte, not original sound
driver entry. Ready is a software acknowledgment, not complete DSP audible
response. Pause and original-NMI-busy states are retained. All1,192 excluded
intervals and reasons implicit in their source game contexts remain auditable.

## Verification and next work

Missing ready and ready-before-receipt trace mutations both fail. Four new
unit tests cover signed decomposition, missing/reordered/overlapping endpoints,
native-rate units and filtering that retains busy states. Full suite:
**1,247 tests pass**, `/tmp/rcr-tests-3062.log`; `git diff --check` passes.
All822 source hashes and the HTML artifact were independently rechecked;
the page was opened and inspected in headless Chromium.

Next work is an observer-neutral original-driver entry/exit and publication
trace on a verified CPU clock, followed by a bounded scheduling experiment
only if supported by that trace. Remaining pulse/triangle contributions at
the frozen waveform events also remain open. Existing speed, picture, menu,
DMA and DSP-ordering gates must be retained. No pop-free or release verdict.
