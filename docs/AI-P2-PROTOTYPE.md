# Opt-in AI-assisted P2 prototype

This is an **isolated, offline experimental cartridge**, not the default build
and not deployed to any MiSTer. The companion runs on the SNES CPU, not in an
emulator input bot. Original graphics, combat, money, shops, item bonuses and
equipment routines remain unchanged. There is no new XP or leveling system.

Main's last recorded AI cartridge is `build/ai-p2-4166/native-cpu.sfc`, SHA-256
`b2136dc1471ffdf87a4671062d7482366641905cc0a6d79fcaa690341e23de8e`
(commit `c77d549`). Tap **R** on the 1P/2P title, the skill screen, or in-game.
Enabling AI forces 2P and shows **AI** next to 2P PLAY. HUD name **AI** in-game.
LEVEL shows one skill name (NOVICE / INTERMED / ADVANCED / GAMER).

Commits on `main` after `c77d549` changed `snes/ai_p2.asm` (skill text, combat,
camera) without publishing a new ROM hash in this file. Those edits are source
on `main`, not a named cartridge.

Branch `ai-p2-4225` is parked on purpose and is **not** merged into `main`.
Its candidate is `build/ai-p2-4225/native-cpu.sfc`, SHA-256
`23fad860cce1660252d1dc61ee9afdeda0116f87020f9feae5ba1ead83808477`.
That branch labels the companion with the P2 name plus **AI** (`RYAN AI` or
`ALEX AI`). Do not treat 4225 as the `main` build.

The named card image **4163** (`build/ai-p2-4163`, SHA-256
`bd62a39387e2281ffb9ab3038ab531a4bfbf6cf1aa9bcea1754146f16cd00ba0`) is 4162
difficulty plus the AI stacked at `e4849b2`. Rebuild it with `make playable`
(see the README). 4166 and 4225 are later than that recipe.

Builds **4236** and **gamer-eyes-4239**, and a separate `snes/gamer_eyes.asm`,
are not in this repository and are not on any pushed branch. They are local
inputs only. `make playable` does not produce them. `main` does contain an
inline `gamer_eyes` routine in `snes/ai_p2.asm`; that routine is not those
cartridges.

Review: <http://127.0.0.1:8766/ai-p2-review-02/>.

## Controls

1. Select the original **2-player** game mode.
2. Tap **R** in the pregame settings screen, or in-game, to toggle AI. It is off
   at reset; a held R toggles once, not repeatedly. While AI is on, the HUD
   shows **AI**. Enabling AI forces 2P.
3. During gameplay, P2 follows P1 and approaches/attacks nearby enemy actors.
   AI never generates Start or Select.
4. Hold **L on controller 1** to lend its controls to P2. Directions, attack/
   confirm/cancel and Select go exclusively to P2; P1 receives no gameplay
   movement or attacks. **Start remains the original global pause control**:
   the original `$F731` routine reads only P1 Start, so sending it solely to P2
   does not open the menu.
5. While holding L, open Belongings and use P2's original inventory. Release L
   to restore P1 after a neutral input poll. If a menu remains open, AI stays
   suspended. Hold L again to continue managing P2, cancel out and unpause.

Physical P2 input takes precedence over AI in the assembly, but this path has
not yet received an actual two-controller integration test. Existing experimental
control presets are rejected by the builder until their serial-read layout is
integrated; this prototype assumes the current nine-bit adapter.

## Executed evidence

The captures below are the earlier isolated prototype whose parent was
`build/sprite-copy-game-3252`, not 4163, 4166, or the parked 4225 branch.
All three of those captures use the same actual cartridge and core:

| Capture | Frames | What it establishes |
| --- | ---: | --- |
| `ai-p2-input-final-02` | 2,329 | Unmodified starting state; only controller 1 input; autonomous P2 movement and attack inputs; original Belongings access; release/reacquire within menu; exit restores P1 and AI. |
| `ai-p2-equipment-final-02` | 2,967 | Explicit synthetic five-byte initialization, then controller 1 equips P2 Boat Shoes, automatically unequips Sneakers, preserves P1 inventory/stats, exits and resumes. |
| `ai-p2-disabled-final-02` | 2,329 | Default-off from authenticated title menu onward; no synthetic P2 held input. Power-on arbitrary WRAM before reset clearing is not misclassified as an enabled feature. |

No adapter faults were recorded. All requested controller 1 inputs were
delivered. These tests do **not** certify full-speed behavior, sound quality,
physical hardware or the entire game. Five focused Python tests pass, including
occupied-code/hook rejection and audit mutations for wrong item owner, wrong
inventory, wrong equipment flags and wrong stat bonuses.

### Synthetic equipment test, precisely

The fixture seeds these original-game bytes once, after reaching gameplay:

| Address | Initial value | Meaning |
| --- | ---: | --- |
| `$064D` | `$23` | P1 Loafers, not equipped |
| `$0655` | `$A1` | P2 Sneakers, equipped |
| `$0656` | `$22` | P2 Boat Shoes, not equipped |
| `$04A4` | 25 | P2 kick: base 15 plus Sneakers' 10 |
| `$04B0` | 35 | P2 defense: base 15 plus Sneakers' 20 |

No other fixture writes occur. P1 uses L+Down and L+A, followed by original
dialogue advancement. The game changes P2 inventory from `A1 22` to `21 A2`,
keeps P2 kick at 25 and raises defense to 45. P1 inventory and kick/defense
remain unchanged throughout. `$059D == 1` independently identifies P2 as the
original item-use owner. The test then cancels, unpauses and restores AI.

These meanings come from the supplied original US ROM: bank 2 `$BDC9`
selects item ownership from P1/P2 A; `$BEDC` removes previous footwear;
`$BF93` sets the worn bit. Item `$21` is Sneakers and `$22` Boat Shoes in the
original item table at `$A4F9`. This is not proof of acquiring the items through
normal shopping, which remains a separate test to add.

## Implementation and limits

`snes/ai_p2.asm` on `main` intercepts cached inputs immediately before the existing fast
serial poll. It preserves X/Y/P, disables NMI during the bounded input operation
and uses private reset-cleared WRAM from `$7FF000` (the assembly currently
touches through `$7FF017`). It selects original enemy
slots 2/3, not object slots 4..7; follows P1 when separated; steers using original
world coordinates, whose ground Y increases toward screen-up. No navigation
search or network/model calls run on the console.

Friendly-fire avoidance, shopping AI, death/revival policy and human P2
takeover still need work. Manual management still requires holding L.

Earlier numbered prototype/capture attempts are retained as failed iterations;
their source hashes can differ from the finalized tools. The captures in this
file are that earlier prototype's evidence, not a certificate for 4163 or for
branch `ai-p2-4225`.

## Reproduce

Named 4163 (AI on difficulty 4162, parent splash 4146, gameplay 4108) is
`make playable ROM=/path/to/the/US/ROM BUILD=4163`. That recipe uses the
builders at `e4849b2` and checks the published SHA-256. It needs local build
3955 or 3800; those cartridges are not in git. The 3252-parent commands below
reproduce the earlier isolated prototype, not 4163.

```sh
python -m tools.build_ai_p2 --parent build/sprite-copy-game-3252 --out build/ai-p2-NEW
python -m unittest tests.test_ai_p2 -v
python -m tools.capture_ai_p2 --candidate build/ai-p2-NEW \
  --core .deps/snes9x-voice-2292/libretro/rcr_voice_edge_libretro.so \
  --out build/ai-p2-input-NEW
# Repeat with --equipment and --disabled into separate fresh directories.
python -m tools.review_ai_p2 --candidate build/ai-p2-NEW \
  --normal build/ai-p2-input-NEW --equipment build/ai-p2-equipment-NEW \
  --disabled build/ai-p2-disabled-NEW --out build/ai-p2-review-NEW
```
