# Start then Select: current local build

The previously reported Start/Select failure does not reproduce in the current
local candidate (`build/sweep-flags-01/native-cpu.sfc`, SHA
`8ef0b2b92bec9954b153ff0978ac4c2381a2e7c82595231be8b72b775d5ed3c4`).
Matched NES/SNES input captures at `build/current-start-select-01/{nes,snes}`
open the lower menu with Start, then replace the health bars with `$20.00`
using Select. The following fixed rectangles match at five-bit RGB precision:

- HUD: x 8–191, y 8–23.
- Lower menu: x 8–255, y 194–223.

Both regions match at idle, after Start, after Select, and after the subsequent
B press. The existing scenario names the last phase `after_exit`, but neither
original nor candidate closes the menu in that capture. That label is not a
behavioral assertion. Actor positions differ and are outside this check.

## Repeatable audit

```sh
python3 tools/menu_audit.py \
  --reference build/current-start-select-01/nes \
  --candidate build/current-start-select-01/snes \
  --out build/current-start-select-01/site
```

The tool verifies the source captures, original reference ROM binding, input
delivery, scenario completion, and absence of adapter faults. It compares the
fixed regions without searching for alignment and requires both the Start-menu
and Select-HUD transitions in each capture. Identical blank captures cannot
pass. Unit negative controls also reject a stale HUD and truncated menu pixel.
All 59 unit tests pass.

The web audit includes the full phase images, both complete audio recordings,
the scoped gate report, and a file-hash manifest. The resulting pass does not
certify menu navigation generally, actor rendering, scrolling, original-speed
timing, audio fidelity, or physical SNAC. No new ROM change was needed for this
reproduction, and the older build running on Rival was not replaced.
