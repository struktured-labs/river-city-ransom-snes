# DRAFT: pull request (not created)

- **Base:** `main` · **Head:** `release-1.0-prep`
- **Title:** Release prep: v0.9.0 beta (build 4304): player README, patch tooling, screenshots
- **Create as:** draft. Merge only after Carmelo approves the release.

## Body

Prepares the first public release of the SNES port as **v0.9.0 beta**. The ROM is
build 4304: build 4302 (tag `build-4302`, `fix-difficulty-x-clobber`: 4295 = 4294 + the
hard-freeze fix and the Gamer stamina bar; then the SNAC fix 4299, the #27 stat fix 4300,
MiSTer savestates 4301 and Gamer stamina saturation 4302) with the SPC engine replaced
by Myself086's Project Nested version (MIT) of Memblers' engine, carrying this port's
SPC fixes (`nested-audio`, 4304).

### What's in this branch
Everything from `rumble-wip`, which `main` does not have yet:
- Gamer outline (4276–4292)
- rumble (4294)
- hard-freeze fix and Gamer stamina bar (4295, `freeze-fix`, see `docs/FREEZE-FIX.md`)
- Limited Run SNAC fix (4299), boss-spawn stat fix #27 (4300), MiSTer savestates #30 (4301),
  Gamer stamina saturates at 255 #31 (4302)
- Project Nested SPC engine with the port's SPC fixes (4304, `nested-audio`,
  `tools/build_nested_ext.py`, `docs/NESTED-AUDIO.md`): NES-matched sweeps, triangle
  attack/release (0 mid-wave cutoffs), noise clock table, timed receiver, restart
  volume, startup pitch; crisper pulse samples
- snes9x and Mesen harnesses

Plus:
- `release/v0.9.0-beta/README.md`: the player README (features, patching and hashes,
  tested-on list, controls, known issues, credits, changelog).
- `release/v0.9.0-beta/screenshots/`: six native 256×224 PNGs (Mesen2, 4294).
- `release/v0.9.0-beta/RELEASE-NOTES.md`, `SUBMISSIONS.md`, `CHECKLIST.md`: drafts
  for the GitHub release and the romhacking sites, plus the go/no-go list.
- `tools/release_patch.py` with `tests/test_release_patch.py`: deterministic BPS
  creation (Flips `--bps-delta`) and an independent applier that checks the source
  CRC, target CRC and SHA-256.

### Not in this branch
- No ROMs, no patch files, no extracted game data. The patch is attached to the
  GitHub release only.

### Verification
- The patch applied to No-Intro `River City Ransom (USA).nes` (CRC32 C3508F7E)
  reproduces the 4304 SHA-256 `369d0066…f9f0` exactly, both with Flips and with the
  independent applier. The headerless variant does the same from CRC32 E9C387EC.
  Applying a patch to the wrong header variant is rejected.
- `python3 -m unittest tests.test_release_patch tests.test_rumble tests.test_gamer_outline tests.test_freeze_fix`
  passes.
- 4304 passes the full Mesen2 suite (outline 1–9, rumble R0–R6, savestate bridge, timing
  max vblank line 257/257, SPC link 0 timeouts) and the freeze batches (0/66 snes9x
  and 0/60 Mesen2 hangs; 4294 froze in 1/66 and 2/60). The fight-dependent snes9x
  outline and rumble scenarios pass with input-shift tolerance, as 4302 needed too
  (`docs/NESTED-AUDIO.md`). 4302 passed the same suite
  (`docs/ISSUES-4302-VERIFICATION.md`). Several checks were made to test what they target, and
  each still fails on a deliberately broken build (`docs/ISSUES-4302-VERIFICATION.md`).
- Forced boss spawns match the NES byte for byte on Novice and Advanced. Intermediate
  is Novice + 8 and Gamer is Novice + 32. Spawns no longer write into Alex's stats
  (#27).
- 4304 has not been checked on MiSTer or real hardware yet (4299 and 4301 were).

### Before merge
See `release/v0.9.0-beta/CHECKLIST.md`: repository or release visibility, the hardware
smoke test, and the go/no-go on known issues. The SPC engine is credited to Memblers
and Myself086 (Laurent Courville) and ships with the MIT notice; no further statement
is needed.
