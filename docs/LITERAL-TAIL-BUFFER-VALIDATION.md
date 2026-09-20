# Publish literal lookahead only at command completion

Retained candidate `build/literal-tail-buffer-01/native-cpu.sfc`, SHA256
`9d72565ce36e59b77343cd9454128b07fec46e38635cded4641b4e0b8f5fca44`.

The guarded literal loop now reads/stores the final lookahead buffer once,
after its last copied byte. The source pointer still advances per byte;
the source-reader mailbox and original game variables retain their final
values. The existing path requires game NMI disabled, so no game interrupt
can observe the omitted intermediate buffer values. Fallbacks are unchanged.

This removes two instructions per nonfinal fast-path byte. Host-only
profiles over raw frames 250..425 report 6483 -> 6013 instructions inside
`bulk_literal_bytes`, with the same 17 entries. Both profiled captures match
their normal-core timeline and WAV byte-for-byte. Evidence:
`build/literal-{parent,tail}-counts-01.csv` and corresponding capture folders.

The frame benchmark is **unchanged**, 1956 total and 165/56/57/478 for
boot/settings/story/street. Settings/story still fail. This is a measured
CPU-work reduction, not a claimed frame-speed improvement. It is retained
because it removes redundant work without adding a guard or widening the
existing critical section; all scoped regression checks pass.

The full adapter suite passes, including the final-buffer omission mutation
failing case 30, and all 117 Python tests pass. The 7552-frame long route
passes café menu/CHR and room-3 camera/scroll checks. All 169395 received
audio bytes match CPU sends. All 7365 packets are acknowledged once per
completed NMI, with no pending writes/tail. Gap histogram remains
1:7340, 2:5, 3:7, 4:3, 5:3, 6:1, 22:4, 32:1.

Normal and observer long captures match timeline/WAV byte-for-byte.
Full audio: `build/literal-tail-long-audio-audit-01/index.html`.
This does not establish perceptual audio fidelity, full-game speed or all
scrolling encounters. No Rival deployment.
