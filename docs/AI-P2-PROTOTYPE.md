# Opt-in AI-assisted P2 prototype

This is an **isolated, offline experimental cartridge**, not the default build
and not deployed to any MiSTer. The companion runs on the SNES CPU, not in an
emulator input bot. Original graphics, combat, money, shops, item bonuses and
equipment routines remain unchanged. There is no new XP or leveling system.

Current candidate: `build/ai-p2-4225/native-cpu.sfc`, SHA-256
`23fad860cce1660252d1dc61ee9afdeda0116f87020f9feae5ba1ead83808477`.
Tap **R** on the 1P/2P title, the skill screen, or in-game. Enabling AI forces
2P and labels the companion with their name plus **AI** (`RYAN AI` or `ALEX AI`,
from P2's 4-letter name — whoever you did not pick as player 1). The original
font has no parentheses. HUD keeps the real name and tags **AI** after P2's bar.
LEVEL shows only the skill name (NOVICE / INTERMED / ADVANCED / GAMER), not an AI tag.

Review: <http://127.0.0.1:8766/ai-p2-review-02/>.

## Controls

1. Select the original **2-player** game mode.
2. Tap **R** in the pregame settings screen to enable AI. It is off at reset;
   a held R toggles once, not repeatedly. No on-screen AI indicator exists yet.
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

All three current captures use the same actual cartridge and core:

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

`snes/ai_p2.asm` intercepts cached inputs immediately before the existing fast
serial poll. It preserves X/Y/P, disables NMI during the bounded input operation
and uses private reset-cleared `$7FF000..$7FF00F` WRAM. It selects original enemy
slots 2/3, not object slots 4..7; follows P1 when separated; steers using original
world coordinates, whose ground Y increases toward screen-up. No navigation
search or network/model calls run on the console.

Combat targeting skips P1's nearest live goon (actor slots 2/3, DX<80 DY<40)
so P2 punches someone else. If that is the only live enemy, P2 follows P1 and
does not punch. Companion never walks against P1's held left/right (so 2P
camera can leave a room). Shopping AI and death/revival policy still need work. Manual
management still requires holding L.

Earlier numbered prototype/capture attempts are retained as failed iterations;
their source hashes can differ from the finalized tools. Only the final captures
listed above and review 02 are the current source-validated evidence.

## Reproduce

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
