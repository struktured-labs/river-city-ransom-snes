# Camera interval profile and rejected grouped scan

Capture `build/camera-cost-02/snes` uses the host-only profile in
`tools/snes9x_cpu_profile.inc`, with RCR_PROFILE_CAMERA_WINDOW=1 and first/
last frame 6833. Exact retained experimental ROM is raster-rearm-02. The
window opens at translated NMI restore $2925 and closes before E2B1's camera
store. It includes intervening IRQ work. Full timeline and WAV compare
byte-for-byte equal to the normal re-arm long capture.

CSV `build/camera-cost-02.csv` counts **10641 instructions**, not cycles.
Broad nearest-symbol totals include native_prepare 1066, prepare_sprites
906, wait_port0 593, generated stubs 489, prepare_chr 441, bank_switch_enter
403, dispatch_write 378, raster_rearm 256 and spc_frame 239. These are not
whole-program cycle percentages or uniquely attributable wall time.

Important correction: native_prepare's 1066 instructions are **not** 1066
flag-scan instructions. Exact scan/loop addresses $86C0..$86E2 contribute
only 25; conversion addresses $86E3..$87E1 contribute 1018. Initial broad
symbol attribution confused scanning with conversion. The next cost work
should target measured conversion/other hot paths, not assume scanning
dominates this camera interval.

An eight-row grouped-scan experiment was nevertheless executed and tested:
only groups with no dirty-shadow bit are skipped; state 1 or 3 falls back,
and array/remaining-budget boundaries are guarded. It passes the independent
executed row oracle for both pattern halves, menu/game budgets and mirroring.
Wrong attribute quadrant and forced dirty-row skipping both fail the oracle.
Evidence: `build/row-scan-oracle-01` and final isolated rerun
`build/row-scan-isolated-02`.

Game measurements were worse: baseline 1954 and long route 7550, each one
frame slower than re-arm parent. The scan is therefore not enabled by any
game build. It remains an isolated opt-in fixture branch
`EXPERIMENTAL_ROW_SCAN`, exercised by `check_rows.py --grouped-scan`.
Rebuilt `build/row-scan-game-revert-01/native-cpu.sfc` compares byte-for-byte
equal to `build/raster-rearm-02/native-cpu.sfc`.

All 125 Python tests pass. No speed/scrolling/audio completion claim and no
Rival deployment. Default ROM remains unaffected.
