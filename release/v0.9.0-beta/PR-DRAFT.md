# DRAFT: pull request (not created)

- **Base:** `main` · **Head:** `release-1.0-prep`
- **Title:** Release prep: v0.9.0 beta (build 4294): player README, patch tooling, screenshots
- **Create as:** draft. Merge only after Carmelo approves the release.

## Body

Prepares the first public release of the SNES port as **v0.9.0 beta**. The ROM is
build 4294 (`rumble-wip` 235d561: rumble + Gamer outline + difficulty modes).

### What's in this branch
Everything from `rumble-wip`, which `main` does not have yet:
- Gamer outline (4276–4292)
- rumble (4294)
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
  reproduces the 4294 SHA-256 `cbe302cf…4fbb` exactly, both with Flips and with the
  independent applier. The headerless variant does the same from CRC32 E9C387EC.
  Applying a patch to the wrong header variant is rejected.
- `python3 -m unittest tests.test_release_patch tests.test_rumble tests.test_gamer_outline`
  passes.
- 4294 passes all Mesen2 and snes9x acceptance checks. It has not been checked on
  MiSTer or real hardware yet.

### Before merge
See `release/v0.9.0-beta/CHECKLIST.md`: Memblers' permission, repository or release
visibility, the hardware smoke test, and the go/no-go on known issues.
