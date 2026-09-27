# v0.9.0 beta go/no-go checklist

## Needs Carmelo (approval or accounts)
1. [ ] Approve the version (0.9.0 beta) and the README wording.
2. [ ] **Memblers' 2A03 SPC700 engine:** get permission and agree the credit wording.
   The binary (`Memblers_2a03.bin`, via upernes, GPLv3) is embedded in the ROM and
   carried as literal bytes in the patch. Its own distribution terms are not
   established. Contact: nesdev forums / Memblers.
3. [ ] **Visibility:** make `river-city-ransom-snes` public, or publish the release
   from a new public repo. Checked 2026-09-27: no .nes/.sfc/.smc/.bin/.spc file
   in any branch's history, and `.gitignore` covers them and `build/`. Before going
   public, still review the `docs/audit` screenshots and the disassembly-derived
   notes and assembly for anything you'd rather keep private.
4. [ ] Consider adding a LICENSE for the port code. The repo has none today.
5. [ ] Hardware smoke test of 4294: MiSTer SNES core 20260603 with a rumble pad on
   port 1 and SNAC off, plus an EverDrive if possible. Boot, menus, one street fight,
   a shop, pause. Update the "Tested on" table.
6. [ ] Go/no-go on the known issues (#4 #5 #6 #8 #9) for a *beta*.
7. [ ] Merge the PR `release-1.0-prep` → `main` (see PR-DRAFT.md).
8. [ ] Create the tag `v0.9.0-beta` and the GitHub pre-release; attach the zip and BPS
   (RELEASE-NOTES.md).
9. [ ] Submit to romhacking.net (account) and romhack.ing (account). Romhack Plaza is
   optional (SUBMISSIONS.md).
10. [ ] Merge the website draft PR (Vercel deploys `main` to strukturedlabs.com).

## Verified
- The BPS patches reproduce 4294 SHA-256 `cbe302cf…4fbb` from the No-Intro ROM,
  with both Flips and the independent applier.
- Mesen2 and snes9x acceptance checks pass. Rumble tests pass in both emulators.
- In Mesen2: SNES A jumps, the same as Y+B.

## Optional before 1.0
- Internal header title `RCR NATIVE CPU PROOF`: rename it (this changes the SHA, so
  regenerate the patch).
- Extended passwords and a full SRAM save (GAMER-MODE spec).
- Gamer stamina HUD scale.
