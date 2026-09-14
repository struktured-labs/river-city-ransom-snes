# Visual audit checkpoint

Private development evidence. No ROMs or raw game assets are published here.
The layout follows the Penta Dragon DX audit approach: reference/candidate/diff
collages, exact evidence hashes and human verdicts attached to those hashes.

## Live game execution — incomplete

Original game code runs on the SNES CPU, advances through menus into the street,
and supplies the SPC700 NES sound engine. These are **not screenshot fixtures**.
NES and SNES input/frame schedules are not synchronized, and scrolling, raster
HUD behavior, speed and audio fidelity remain incomplete. Scores expose the
differences; the live audit correctly does not claim a visual/gameplay pass.

![Live NES / SNES / difference collage](live/collage.png)

[Evidence](live/audit.json) · [Menu receipt](live/menu-receipt.json) ·
[Street receipt](live/street-receipt.json) · [12,000-frame soak receipt](soak-receipt.json)

## Renderer-only fixtures — three pixel passes

These separately test original CHR, nametables, attributes, sprites and palette
conversion on native SNES hardware. Each comparison has zero RGB555 mismatches
over the top 239 NES rows. This does **not** prove gameplay or timing compatibility.

![Static NES / SNES / difference collage](renderer/collage.png)

[Renderer evidence](renderer/audit.json)

## Review and reproduce

GitHub renders these collages privately. Download/open the corresponding
`live/index.html` or `renderer/index.html`, or use the loopback server in the
[runbook](../DEVELOPMENT.md), for zoomable images and per-evidence review notes.
Export review JSON before sharing feedback. GitHub itself does not execute the HTML.

```sh
python3 tools/verify_audit.py docs/audit/live
python3 tools/verify_audit.py docs/audit/renderer
```

Public Pages is disabled. Automatic approval review rejected public publication
from the private repository; explicit visibility approval is still required.
