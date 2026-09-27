# DRAFT: romhacking site submissions (not submitted)

Upload or link `river-city-ransom-snes-v0.9.0-beta.zip`, which holds both BPS
patches, README.md and CHECKSUMS.txt. Every site needs Carmelo's own account.

Screenshots (native 256×224 PNG, in `screenshots/`): title shot
`02-title-mode-select.png`; others `04-street.png`, `05-gamer-outline.png`,
`03-skill-select-gamer.png`, `06-combat.png`. The splash, `01-splash.png`, is
optional; sites want game shots.

---

## 1. romhacking.net (RHDN): Hacks → Submit

RHDN hosts nothing itself; it takes a **direct download link**.

- **Title:** River City Ransom SNES
- **Game:** River City Ransom (NES)
- **Platform:** NES (the patch applies to the NES ROM; the output is a SNES image)
- **Category:** Complete. If the form has a port-specific option, use that. This is a
  platform port, not a new game.
- **Mods:** Gameplay, Graphics (palette/outline), Other (platform port, rumble, SNES audio)
- **Genre:** Action / Beat 'em up
- **Patch version:** 0.9.0 beta
- **Release date:** set on the day it is published
- **Status:** In progress (beta)
- **Author / Credits:** struktured labs (port). Memblers (Joey Parsell), with Kevin
  Horton and others: 2A03 SPC700 sound engine.
- **Download link:** https://github.com/struktured-labs/river-city-ransom-snes/releases/download/v0.9.0-beta/river-city-ransom-snes-v0.9.0-beta.zip
- **Website:** https://strukturedlabs.com/projects#gaming
- **ROM / ISO Information** (one per line):
```
Database match: River City Ransom (USA)
Database: No-Intro: Nintendo Entertainment System (v. 20160927-030708)
File/ROM SHA-1: A8612A36D9D2739D2B321B6EBB97C2757CCCA410
File/ROM CRC32: C3508F7E
ROM SHA-1 (without header): CA794E6A2B0ECF69B2BE1753D379CCE6434C49D7
ROM CRC32 (without header): E9C387EC
```
- **Description:**
```
River City Ransom, ported natively to the Super Nintendo.

The original game code runs directly on the SNES CPU; this is not an emulator
cartridge. Graphics are converted to SNES tiles and palettes, and the NES music and
sound effects play on the SNES audio chip through Memblers' 2A03 SPC700 engine. The
patch turns the US NES ROM into a 2 MB SNES image that runs on SNES emulators, flash
carts and the MiSTer SNES core.

New in this port:
- Two new difficulty levels. Intermediate sits between the original Novice and
  Advanced. Gamer gives enemies +32 and higher stat caps (combat/will 127, stamina
  255), raises your caps too, and makes agility above 63 actually faster. You can
  still win at the original stats.
- On Gamer, gang members get a red outline so you can read the crowd.
- Rumble on controller 1 with the MiSTer SNES core (SNES Rumble protocol).
- Dedicated jump button (A) alongside the original Y+B.

This is a beta. Known issues: occasional audio pops, some slowdown in busy scenes
and two-player fights, brief sprite glitches, shop text and colour differences, and
the Gamer stamina bar looks full above 63. See the readme.

Tested in Mesen2 and snes9x. Patch with Flips or Rom Patcher JS. A headered and a
headerless BPS are both included.
```

---

## 2. romhack.ing (RHDI): Submit → Hack

The patch zip is **uploaded through the site**. Use the built-in hasher on the clean
ROM to fill in the DAT information.

- **Title:** River City Ransom SNES
- **Game:** River City Ransom · **Platform:** NES
- **Tags:** Hack · Gameplay · Graphics · Port. Pick the closest if there is no Port tag.
- **Version:** 0.9.0 beta · **Status:** Beta / In progress
- **Authors:** struktured labs. **Additional credits:** Memblers (2A03 SPC700 engine),
  Kevin Horton and others.
- **License:** "All rights reserved / patch only". Do not pick an open license until
  the Memblers engine terms are confirmed.
- **DAT information:** `River City Ransom (USA)`; SHA-1 `A8612A36D9D2739D2B321B6EBB97C2757CCCA410`;
  CRC32 `C3508F7E` (No-Intro, headered file)
- **File:** river-city-ransom-snes-v0.9.0-beta.zip
- **Description:** same as RHDN above.

---

## 3. Romhack Plaza (optional)

- **Title:** River City Ransom SNES
- **Game:** River City Ransom · **Platform:** NES · **Type:** Improvement / Port
- **Version:** 0.9.0 beta
- **Patch:** upload the zip or `river-city-ransom-snes-v0.9.0-beta.bps`
- **Hashes:** No-Intro `River City Ransom (USA)`, CRC32 `C3508F7E`,
  SHA-1 `A8612A36D9D2739D2B321B6EBB97C2757CCCA410`
- **Description:** same as RHDN (English; use the game name "River City Ransom").
