# Avoid redundant graphics-command ring publication

`bulk_ring_bytes` now compares each command byte against the mapped PPU
shadow. Identical bytes skip the store and dirty bookkeeping, including
the temporary X save; ring index, PPU address, write accounting, Y countdown
and final ABI still advance. Changed bytes use the existing path.

Executed case 17 repeats five identical bytes across the 64-byte ring wrap
and PPU page boundary, with both mirrored rows clean. No dirty state is
introduced, all five writes are counted and the final ring index is checked.
The existing 256-byte/stride-32 and changed-write tests remain. Missing-store
and removed-unchanged-branch mutants both fail case 17. Complete adapter,
video and 103 unit tests pass.

Candidate `build/unchanged-ring-01/native-cpu.sfc` SHA:
`09217cf50e86989a7ec7c58036a469b7113a1fd4c76f0bc614b389ea69be1e91`.
Baseline `build/unchanged-ring-quality-01/snes` completes 2,047 frames,
two fewer than the length-gated parent. This remains slower than NES.

The full café/exit route completes 7,643 frames. The café's 17,380-pixel menu
still matches (`build/unchanged-ring-shop-audit-01/index.html`), as does the
20,480-pixel fixed room-3 strip at matched camera zero
(`build/unchanged-ring-camera-audit-01/index.html`). The shop checker now
selects the explicit `observe_shop` checkpoint rather than assuming the
final frame is inside the café, allowing the verified extended route too.

No change to audio eligibility or the SPC engine. The earlier audio fix
remains in this candidate, but no new full audio-fidelity claim is made.
Original speed, complete scrolling and remaining popping are still open.
Nothing deployed to Rivalmage.
