# Current tear-free candidate: first-room load profile

This is diagnosis, not a new ROM or a speed pass. Candidate remains
`camera-safe-on-521`, SHA256
`43c8f5a8213844bb33624a3a980b67d14f39b9a8b0cc045560d7c66c330e3929`.
No Rival reset/deployment. First-room loading remains21 frames versus NES20.

Fresh `camera-safe-load-531` traces instructions and stage entries at frames
2110–2132 while completing the entire9,409-frame fixed-input route. Complete
timeline and PCM match independent normal capture `camera-safe-fixed-524`.
No observer/core changes or altered gameplay inputs.

## Before rendering is enabled

`camera-safe-load-cost-533` bounds the window by the original mask-state
edges: room change/rendering off2110, enable2124. Total observed instruction
intervals:5,004,166 master clocks. These are frame-boundary measurements,
not exact intra-frame write-to-write durations or exclusive CPU costs.

| Observed region | Own elapsed master clocks |
| --- | ---: |
| Original FC73 wait branch |858,594|
| Rectangle fills |765,374|
| Compressed source reader |581,256|
| Literal copies |239,156|
| CHR pointer resolver |165,312|
| Page fills |145,746|
| Buffered PPU reads |2,760|

This table is selected regions, not an exhaustive partition. The reader's
nested resolver is counted separately. FC73 is46,192 executions of the
unchanged original `D0 FE` self-branch. The auditor verifies both linked ROM
bytes and observed opcode, restricts bank/window, and rejects missing waits
or non-increasing clocks. Intervals can contain boundary event overhead.
Four new tests cover these properties; all492 Python tests pass. **Wait time stays in the acceptance
measurement**; it is not removed to manufacture a speed improvement.

## After rendering enable, before first fade service

`camera-safe-first-cost-532` measures the original first main-loop calls,
matching entry/return stack and subtracting only completely observed ordinary
NMIs for diagnostic attribution. Main iteration begins2125,line169; first
fade-service entry2127,line208. Fade-service entry is not first visible color.

The actor call C78000 takes636,634 elapsed master clocks, of which411,496
(about65%) are ordinary NMI spans. Residual225,138 is not exclusive actor CPU
cost: DMA/events can remain. Sprite-list construction takes76,752 with no
ordinary NMI interruption. Thus inclusive actor time alone would materially
misidentify this bottleneck.

`camera-safe-rows-cost-532` independently records hidden row conversion:
117,374 /116,944 /117,392 /43,408 clocks on frames2125–2128. These are nested
stage costs and must not be added again to inclusive NMI/call totals.

Next optimization should target measured conversion/producer or decode work,
then rerun full loading, rendering, audio and status gates. Smaller individual
costs do not guarantee crossing the next frame deadline. Keep the safe-camera
publication guard, original waits, fade timers and existing failed gates.

Review: `http://127.0.0.1:8766/camera-safe-load-review-534/`.
