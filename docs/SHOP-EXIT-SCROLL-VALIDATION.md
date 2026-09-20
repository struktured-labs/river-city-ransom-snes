# Café exit and scrolling into the next area

`traversal-shop-exit` appends B for 12 frames, 180 idle, Down for 60,
and eight 120-frame Right phases to the verified café route. Prefix/input
tests bind this schedule. No save states, RAM writes, invincibility or
collision bypass are used.

Captures `build/shop-exit-route-01/{nes,snes}` complete 7,532/7,645 frames.
Both leave the café and move from original room ID 2 to 3. At checkpoint
`mall_right_03`, both camera and 9-bit scroll equal zero; the fixed background
strip `(0,32)-(256,112)` matches all 20,480 RGB555 pixels without masking
actors or searching for alignment. At `observe_shop_exit`, the same strip
retains 32 differences. Full images remain in the web audit:
`build/shop-exit-camera-audit-02/index.html`.

The camera auditor now rejects different original room IDs even when their
camera positions coincide. Equal room IDs alone still do not establish
equal scenes (the café shares ID 2 with the street), hence explicit source
images and named checkpoints remain necessary.

By the final checkpoint, combat states have diverged: the original reaches
camera 217 in room 3 while the port remains at camera zero with Alex losing.
That endpoint is not a valid equal-state movement-speed comparison. It is
retained, not discarded in favor of the passing earlier strip. Reaching the
next area demonstrates that this route is not blocked at the mall boundary;
it does not certify all scrolling or original gameplay speed.

`build/reference-shop-exit-01` is a 7,800-frame source-ROM-bound FCEUX replay
of the original input capture. Adding it to the six prior traces introduces
no new hardware patches (still 242 patches/44 stubs). The resulting
`build/shop-exit-coverage-01/native-cpu.sfc` is byte-identical to
`length-gate-01`, SHA
`9291077b107224fe61ea950860a2c567a26ac6eebbcf850b22556255693207e3`.
No additional trace-coverage fix was necessary for this observed exit path.
Audio, speed and later combat/scene fidelity remain open. No Rival reload.
