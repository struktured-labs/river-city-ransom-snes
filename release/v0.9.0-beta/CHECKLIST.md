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
5. [ ] Hardware smoke test of 4302: MiSTer SNES core 20260603 with a rumble pad on
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
- The BPS patches reproduce 4302 SHA-256 `3d8b6112…5f16` from the No-Intro ROM,
  with both Flips and the independent applier.
- 4302 passes the full Mesen2 and snes9x suite (`docs/ISSUES-4302-VERIFICATION.md`):
  - Mesen outline checks 1–9 pass in the full run, and check 9 also in the focused run.
  - snes9x outline 9/9.
  - Rumble: Mesen R0–R6 and snes9x S0–S4.
  - Savestate bridge.
  - Timing: max vblank line 257 default / 258 Gamer, nothing ends in active display.
  - Freeze batches: 66 snes9x and 60 Mesen2 runs, 0 hangs.
  - Unit tests: 1644, with 1 known unrelated failure in `test_chromatic_wub`.
- Several checks were fixed in 4302 so they test what they target (S1 forced-boss phase,
  blank-frame handling, coherent OAM lag, goons on screen for 5/6, per-attempt
  counters for 9, liveness by joypad polls). Each still fails on a deliberately
  broken build.
- Issues fixed and verified against the NES original: #27 boss-spawn stat corruption
  (4300; also the cause of #24 and #25), #30 MiSTer savestates (4301), #31 Gamer
  boss stamina (4302).
- In Mesen2: SNES A jumps, the same as Y+B.
- Hard freeze on room change mid-fight fixed in 4295: 0 freezes in the 66-run snes9x
  and 60-run Mesen2 reproduction batches (4294: 1 and 2), and still 0 on 4302.
  See `docs/FREEZE-FIX.md`.
- [x] Gamer stamina HUD scale (4295): the bar scales over 0–255, checked by a 0–255 sweep.

## Optional before 1.0
- Internal header title `RCR NATIVE CPU PROOF`: rename it (this changes the SHA, so
  regenerate the patch).
- Extended passwords and a full SRAM save (GAMER-MODE spec).
