# v0.9.0 beta go/no-go checklist

## Needs Carmelo (approval or accounts)
1. [ ] Approve the version (0.9.0 beta) and the README wording.
2. [x] **SPC engine terms:** 4304 uses Myself086's Project Nested version of Memblers'
   2A03 engine (MIT, revision `cc2c892`) instead of the upernes binary. Carmelo decided
   that crediting Memblers and Myself086 (Laurent Courville) plus the MIT notice
   (README and `THIRD-PARTY-NOTICES.txt` in the zip) is enough.
3. [ ] **Visibility:** make `river-city-ransom-snes` public, or publish the release
   from a new public repo. Checked 2026-09-27: no .nes/.sfc/.smc/.bin/.spc file
   in any branch's history, and `.gitignore` covers them and `build/`. Before going
   public, still review the `docs/audit` screenshots and the disassembly-derived
   notes and assembly for anything you'd rather keep private.
4. [ ] Consider adding a LICENSE for the port code. The repo has none today.
5. [ ] Hardware smoke test of 4304 (copied to rivalmage as `RCR-SNES-4304-nested-audio`): MiSTer SNES core 20260603 with a rumble pad on
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
- The BPS patches reproduce 4304 SHA-256 `369d0066…f9f0` from the No-Intro ROM
  (headered and headerless), with both Flips and the independent applier; the wrong
  header variant is rejected. The 4302 kit is kept in `superseded-4302/`.
- 4304 (Project Nested engine + port SPC fixes, `docs/NESTED-AUDIO.md`): triangle
  mid-wave cutoffs 0/0/0, mix clicks 0/0/0, title sweeps 11/12 matched at 1 cent median
  (same as 4302), noise centroid equal to 4302, crisper pulses. Full suite: Mesen
  outline 1–9, rumble R0–R6, bridge, timing 257/257, SPC link 0 timeouts; freeze
  batches 0/66 snes9x and 0/60 Mesen2; snes9x outline and rumble pass with input-shift
  tolerance; unit tests 1659 with the known `test_chromatic_wub` failure.
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
