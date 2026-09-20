# Direct cached-pad polling: a real saving, not a scrolling fix

Candidate726 SHA256
`ec39f1b42134821b80ac4dae846fe2833b99622f0652d23a1f6aa23d166d2a4d`
adds default-off `--experimental-joypad-poll`. It has not been deployed to
Rival. No hardware input, restart, OBS setting, artwork, button mapping or
sound-engine change occurred. The speed/scrolling/audio goal remains open.

## Measured source of wasted work

The unchanged adapter latches both physical SNES pads on the original falling
strobe and maps their buttons to cached NES serial bytes. Original `$FD8E`
then consumes these bytes through sixteen generic hardware-read transactions.
Those transactions repeatedly save/restore adapter state, classify a known
address, and manipulate interrupt policy to read an already-cached bit.

The new helper replaces only `$FD8E..FDA2`, after the original strobe and
`LDX #8`. Cached bits are shifted directly into the original `$EE/$EF` bytes.
The expansion bytes, final carry, A/B/X/Y/P, DP/DB, cache fill bits and mailbox
are preserved. A nonzero strobe still reads the live physical ports. Existing
jump mapping, Select/Start behavior and later edge detection remain untouched.

Unlike the old per-read transactions, the helper masks NMI for the complete
short loop and reapplies the existing depth/bank-pair enable guards at exit.
This is a bounded critical-section change, **not** proof of arbitrary interrupt
interleaving equivalence. No actual SNAC qualification has been performed.

Patch audit730 proves the executed 106-byte helper occupies unused padding,
all 68 prior runtime symbols stay fixed, and only 879 cartridge bytes differ:
eight helper copies, nine entry jumps and checksum. The disabled build is
byte-identical to parent608.

## Executed input and timing oracles

- Oracle729 compares real generated legacy read stubs with the new helper
  for all 65,536 cached pad pairs, varied old game bytes/registers/flags and
  eight mirrored program/data banks. All 32-byte snapshots match an
  independent bit-order/register oracle. Unrelated zero-page bytes are guarded.
- Five compiled mutants are rejected: wrong bit order, lost cache fill ones,
  wrong final carry, wrong mailbox, and missing expansion-byte clear.
- The first run726 failed because its small mutant sample held pad1 at zero,
  allowing reversed pad1 bit order to survive. That failed run is retained.
  The corrected mutant matrix varies all 256 values on **both** pads; a unit
  test protects that coverage. Only the fresh complete729 run is qualified.
- Another 256 cases exercise live-strobe fallback with no buttons held.
  Audit733 additionally runs the actual legacy/fast ROMs with nonzero physical
  libretro inputs on each port separately: 512 matched cases. This is emulator
  port testing, not a real controller or MiSTer capture.
- Timing730 executes 8,192 matched cached-poll calls at actual JSR/return
  boundaries, with complete WRAM identical between normal and timing cores.
  Mean elapsed clocks drop from 22,056.84 to 2,262.83, saving 19,794.01;
  minimum saving is 19,586. This is about 90% of this loop, not of gameplay.

## Main-loop profile and whole-route rejection

The new `audit_main_work.py` binds complete pre-camera original JSR calls to
matching return PC/stack. It subtracts only observed hardware-NMI entries with
matched RTI stack restoration and retains trailing incomplete calls. Camera
hook work is excluded because it can service a retained original NMI.
Entry-edge and DMA/event time can remain outside the subtracted intervals.

Parent650 and candidate731 instruction captures match their respective full
normal timelines and PCM. In the same frame-number window7400–7465, control
caller `$F282` averages 29,152 versus 8,089.64 clocks over 33 calls. Actor work
outside observed NMIs remains the largest pre-camera cost: about145,153 and
156,960 clocks respectively. **Different encounters mean the actor figures
are not an equal-work speed comparison.** Candidate main starts still vary
across lines54–107 and camera stores across24–232.

Normal727 and renderer727 each complete 8,695 frames with identical complete
timelines/PCM. Renderer728 covers all 7,380 eligible frames with zero split
and checks 6,421 unchanged-camera frames with zero stale hold. This run has
no missing renderer coverage, but that does not certify scrolling cadence.

| Uniform two-pixel one/three-frame camera pairs | East | West |
| --- | ---: | ---: |
| Original NES | 3 | 0 |
| Parent608 | 11 | 18 |
| Cached poll726 | 24 | 20 |
| Cached poll + fused sprite position730 | 20 | 6 |

The combination uses candidate730 SHA256
`b6f167120a93a36f941e2ec91c2dfd35f6b5708d66fd3aca47b415d5f5e1c9c4`.
Its 8,695-frame normal/renderer timelines and PCM also agree. It improves
the return trip, but not the outward trip. Neither candidate is promoted.
All hold distributions, long stops and censored boundaries remain in the
reports; route frame totals are not used as a gameplay-speed score.

Room-entry whole loads are 21/29/28 for poll726 and21/28/28 for combination730,
versus NES20/31/30. The first load and fixed-offset fade comparisons fail.
No new Present Status/shop, acoustic, controller-preset or full-game acceptance
is claimed for either candidate. The separately tested noise correction was
not included.578 unit tests and `git diff --check` pass; bound oracle, timing,
patch and main-work source hashes were checked against current files.

Next work must coordinate the main-loop release and camera deadline while
retaining these measured savings. The earlier second-tick deferral alone was
rejected; any combination needs fresh full-route checks, not an assumption
that individual savings add up to a valid scheduler. The original-speed gate
continues to prevent a premature Rival restart.

Review: <http://127.0.0.1:8766/joypad-poll-review-734/>.
