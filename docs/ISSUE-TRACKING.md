# User reports and requested QoL

Repository: https://github.com/struktured-labs/river-city-ransom-snes/issues

Backfilled on2026-09-19 after checking all open and closed issues. Multiple
messages about the same symptom are consolidated; historical fixes are labeled
rather than represented as newly reproduced failures. Local tests do not imply
a pushed build or new hardware verification.

| Issue | Scope |
| --- | --- |
| [#1](https://github.com/struktured-labs/river-city-ransom-snes/issues/1) | Original native-port objective |
| [#2](https://github.com/struktured-labs/river-city-ransom-snes/issues/2) | AI P2 companion parked 2026-09-23 (better, still bad; no pathfinder; not in the no-AI ROM). Earlier EverDrive image was 4163. Branch `ai-p2-4225` is not merged. |
| [#3](https://github.com/struktured-labs/river-city-ransom-snes/issues/3) | SNES/Struktured Labs branding and attribution |
| [#4](https://github.com/struktured-labs/river-city-ransom-snes/issues/4) | Blank Present Status statistics |
| [#5](https://github.com/struktured-labs/river-city-ransom-snes/issues/5) | Original-speed gameplay, rare slowdown, sprite latency |
| [#6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6) | Audio stutter/pops/silence and capture acceptance |
| [#7](https://github.com/struktured-labs/river-city-ransom-snes/issues/7) | Scrolling and right-edge movement |
| [#8](https://github.com/struktured-labs/river-city-ransom-snes/issues/8) | Transient sprites, setup heads, mall NPCs |
| [#9](https://github.com/struktured-labs/river-city-ransom-snes/issues/9) | Shop text/palette/YES-NO visibility |
| [#10](https://github.com/struktured-labs/river-city-ransom-snes/issues/10) | Lingering cursors and their regression coverage |
| [#11](https://github.com/struktured-labs/river-city-ransom-snes/issues/11) | SNAC/Select/Start-Select coverage |
| [#12](https://github.com/struktured-labs/river-city-ransom-snes/issues/12) | Selectable controller modes/dedicated jump |
| [#13](https://github.com/struktured-labs/river-city-ransom-snes/issues/13) | Logo duration and descending slow-WUB splash sound (4146 on EverDrive for listen) |
| [#14](https://github.com/struktured-labs/river-city-ransom-snes/issues/14) | Hardened focused test cycle and reusable skill |
| [#15](https://github.com/struktured-labs/river-city-ransom-snes/issues/15) | Controller-one management of P2 equipment |
| [#16](https://github.com/struktured-labs/river-city-ransom-snes/issues/16) | Immediate shop stat-gain display |
| [#17](https://github.com/struktured-labs/river-city-ransom-snes/issues/17) | Closed: no RCG-style consumed-item marker (food stats stack) |
| [#20](https://github.com/struktured-labs/river-city-ransom-snes/issues/20) | Intermediate difficulty (`$064C=4` +8 in 4162; the EverDrive image that includes it is combined 4163, not a standalone 4162 file) |
| [#21](https://github.com/struktured-labs/river-city-ransom-snes/issues/21) | Gamer Mode (`$064C=3` +32, 127/255; LEVEL GAMER; in 4162 and on the 4163 card image; 44-char encode/decode is still only `tools/rcr_password.py` length classification) |
| [#22](https://github.com/struktured-labs/river-city-ransom-snes/issues/22) | Simon easier on Advanced? original NES overflow check (ROM: no wrap; Advanced is +16 with 63/127 caps) |

The user's progression clarification is part of16/17: defeating gangsters yields
currency, not experience; improvement comes from purchases and equipment. Repeat
stamina/willpower recovery must remain distinct from reported one-time combat
stat benefits. Original code/replay verification is required before changing
marker semantics or claiming a first-use-only rule. No new XP/economy system.

Subsequent ordinary-input original-NES and SNES3252 replays demonstrate Waffles
grants Agility15→16→17 and Strength15→16→17 over two consumptions. Both versions
display the in-shop "AGILITY 1 UP." dialogue. The user confirmed the same on
hardware 4108: food combat stats can be boosted on every purchase, unlike
River City Girls. User asked to drop the marker feature; #17 is closed.

`docs/reported-issues.json` contains the backfilled reports. The explicitly scoped
`python -m tools.sync_reported_issues` is a read-only dry-run; `--apply` creates
only missing exact-title issues after searching open and closed items. It does
not overwrite existing bodies or close issues. For a new report, inspect existing
issue semantics before adding a new entry. The reusable `romhack-test-loop` skill
also includes this tracking requirement when the user requests issue tracking.
