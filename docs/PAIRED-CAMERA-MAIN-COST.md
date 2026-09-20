# Main-thread interval before the camera store

Exact ROM: paired-game-01, SHA256
`c06511b87e82b8daf184b9016e14b86396aa90588033d2ec89467b553208ae21`.
Linker symbol `@restore` is $28F4; this follows the NMI return hook's sound
and graphics work. Host instruction profiling opens there and closes before
E2B1 (camera low-byte store), or at FF4F if the next original NMI intervenes.
It does not mix the next NMI body into an unfinished camera interval.

At raw frame 6821, original game camera changes from 108 to 110:

| Boundary | Scanline | Master clocks within line |
| --- | ---: | ---: |
| C7:28F4 restore entry | 135 | 898 |
| C7:E2B1 camera store | 167 | 1090 |
| C7:FF4F next original NMI entry | 255 | 350 |

Restore-to-camera takes 43840 master clocks (32 ordinary scanlines plus
192 clocks). No short line or frame wrap is crossed. The instruction
profile records 2018 instructions in that interval: 190 below $8000 in
translated runtime, 1258 in original banked code $8000..BFFF, 570 in original
fixed code $C000..FFFF. These are counts, not cycle-share percentages.
Bank C5:A38D..A39A is the hottest repeated sequence (11 executions per PC).
Do not optimize that code on this evidence alone: its original gameplay
semantics still need inspection.

The important scheduling constraint is two-part: the port does not release
the main thread until line 135 in this sample, and after release it still
needs about 32 scanlines to compute the camera. Scheduling a worker merely
after line 30 cannot by itself guarantee that this camera is ready for the
street band. This sample is not proof that every game tick has the same
workload, nor an exact NES instruction-sequence comparison.

Evidence: `build/paired-main-cost-01.csv` profiles frames 6700..6900;
`paired-main-scroll-01.csv` identifies the camera-110 store. The tighter
repeat uses `paired-main-cost-02.csv`, `paired-main-boundary-02.csv`, and
`build/paired-main-cost-02/snes`. Both observer captures reproduce the normal
paired-game long-route WAV and full timeline byte-for-byte.

The reusable fragment `tools/snes9x_cpu_profile.inc` now accepts a hexadecimal
`RCR_PROFILE_RESTORE_PC` and optional `RCR_PROFILE_BOUNDARY_TRACE`. Resolve
the address from the exact ROM's linker labels. The isolated core binaries
are `rcr_camera_main_libretro.so` and `rcr_camera_boundary_libretro.so` under
`/tmp/rcr-snes9x/libretro`; no default ROM or Rival change.

Next work must address early NMI publication/return timing together with
deferred preparation. Moving the entire worker later was already rejected;
small sender savings alone cannot close this camera deadline.
