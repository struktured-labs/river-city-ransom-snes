# Five-clock pulse pitch publication

Follow-up: [Rival hardware trial and retained capture failures](WORD-PITCH-RIVAL.md)
now document this candidate running as a test build. The report below records
its preceding offline qualification.

September 18, 2026. **Offline candidate, not deployed.**
[Actual DSP latches, native A/B audio and unchanged game screenshots](http://127.0.0.1:8766/word-pitch-review-1711/).

## Implemented change

The current balanced publisher exposes low/high pitch bytes eight SPC clocks
apart. The new sequence preloads low into X and high into Y, sets A to the
high-pitch register address, writes low through `$f3`, then executes
`MOVW $f2,YA`: A selects the high register and Y supplies its data. Actual
SPC/DSP traces verify a **five-clock gap**. This remains non-atomic.

The new sequence takes one extra clock and one extra byte. Replacing one
redundant three-clock direct-page read in the existing pointer preparation
with a two-clock, one-byte NOP balances both. No helper, sample, upload-size,
stack or game CPU change is required. X/Y remain scratch; immediate following
instructions overwrite A/flags. Full-game execution qualifies the sampled
callers, not every possible game path.

Only 46 cartridge bytes differ, all inside two checked 40-byte SPC regions or
the cartridge checksum. No graphics, control modes, splash or sample assets
change. Candidate:
`build/word-pitch-1699/game/native-cpu.sfc`, SHA256
`0e9ba29becef5dc548a81d016d0e0311731244a3fc2cc8292db321c9dd2ac12d`.

## Executed checks

- All **50,265** tested period/control/enable/envelope cases retain identical
  direct-page RAM and final DSP state, at identical total SPC call cost.
- A real executed wrong-high-prefetch mutation fails **3,641** cases.
- All sixteen continuous-clock cases pass, covering two frame modes and four
  sender delays on both engines. No bad volume writes.
- Exact hardware episode replay: **1,238** received packets match, byte for
  byte. All **46,300** DSP writes preserve register, value and order. Only
  **8,188** low-pitch writes move three clocks later; every other write and
  all receipt/ready timestamps remain unchanged.
- Both replay observers preserve WAV, timeline, RAM and final image; raw DSP
  DAC output equals delivered PCM. Both retain zero wrong first pitches and
  zero stale nonzero note onsets.

Every measured pulse sample is reconstructed from its actual DSP read phases:

| Same 8,190 pitch transactions | Current engine | Word-write candidate |
| --- | ---: | ---: |
| Mixed-byte pitch samples | 40 | 27 |
| Mixed-byte samples with nonzero voice contribution | 18 | 12 |

Thirteen baseline split samples disappear, 27 remain and none is introduced.
These are **not audible-pop counts**. The three largest baseline nonzero
deviations remain, and are deliberately shown in the review alongside the
largest eliminated nonzero event. These isolated DSP excursions do not explain
the earlier 10–30ms physical silence intervals.

## Full-game regression

Normal1705 and DSP1707 each complete **9,406 frames**. The candidate exactly
matches current production capture1494 in every nonaudio timeline field:
video/frame-image hashes, game RAM, input, NMI, native state and waypoints.
Audio callback sample counts and starts also match exactly—unlike the earlier
17→8-clock trial's retained callback-boundary failure. Audio content is allowed
to change and is not presented as identical.

The independent DSP observer matches the candidate's complete normal timeline
and PCM. All **8,950** actual packets and **1,638** restart orderings pass;
the late-configuration negative control is detected. The complete **379,784**
DSP commands retain values/order: exactly **47,588** low-pitch writes move
three clocks later; the other **332,196** write clocks are unchanged. All
receipt/ready records remain identical.

This route therefore introduces no observed graphics, scrolling, cadence or
callback regression relative to production. It does **not** certify original
NES speed, all encounters, all caller paths, or hardware/perceptual benefit.
The remaining rare slowdown and broader fidelity gates stay open.

## Harness and handoff

`build_word_pitch_trial.py` checks exact preimages and cartridge/engine identity.
`check_word_pitch_trial.py` binds actual executed equivalence, negative controls,
same-command DSP timing and strict complete-game timeline comparison.
`build_word_pitch_review.py` also checks the full-game DSP timing and exact
cartridge change allowlist. New unit tests reject preimage/caller changes,
out-of-contract DSP writes, video/RAM/input-state changes and callback shifts.
**929 tests pass.** Native clips use identical absolute sample windows without
retiming, resampling, gain matching or normalization.

Review1709 failed because its collage assumed 224 rather than the captured
239 lines; no gameplay evidence was affected. Review1710 preceded the added
eliminated-event example; **1711 is authoritative**. Failed/historical output
was retained, not deleted. The initial builder preimage check also correctly
rejected an oversized sequence before creating any output.

Rival remains on regular cartridge `777635fa6d86`; no MiSTer/OBS input, restart
or configuration mutation was performed in this iteration. The next promotion
gate is a controlled hardware A/B with the current cartridge retained for
rollback. Neither the reduced latch-error count nor passing emulator gates
alone proves audible improvement or completion of the port.
