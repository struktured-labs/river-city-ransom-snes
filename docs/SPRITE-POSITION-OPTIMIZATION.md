# Fused sprite positioning: correct and faster, not a release candidate

Candidate720 SHA256
`7e6400594a4ee3260ffaa9256a55e83a7413b58fb404451339f12fc561e630fe`
adds default-off `--experimental-sprite-position`. It is not on Rival. No
hardware inputs, restart, OBS changes, audio changes or original-art changes
were made. The speed/scrolling/audio goal remains incomplete.

## Implementation and executed checks

The replacement fuses the original `$EEEE..EF25` signed sprite-offset lookup,
optional horizontal flip and coordinate addition. It removes redundant
intermediate stores and indexed-loop bookkeeping, while retaining 8-bit ADC
semantics, including SNES decimal mode. It does not change game ticks or
interrupt scheduling. The older `--experimental-sprite-coordinates` replaces
only the final addition loop; the two options are mutually exclusive.

The new 56-byte helper is appended in unused runtime padding. Patch audit722
proves all 68 existing global runtime labels remain fixed and exactly 488
cartridge bytes change: qualified helper copies, entry patches and checksum.
The disabled build reproduces parent608 byte-for-byte.

Oracle719 executes original and replacement for all 65,536 offset pairs,
varying origins, flip, table index, flags and registers across eight banks.
All 32-byte result records match; 32,768 binary-mode cases also match an
independent arithmetic/register oracle. Six executed mutants are rejected:
wrong flip, missing carry clear, wrong Y origin, wrong exit flags, missing
table-index increment and altered decimal mode. Unrelated zero-page state,
source operands and caller registers are checked. No interrupt is injected
inside this isolated fixture; it is not an interrupt-interleaving proof.

Timing720 measures 8,192 matched executions, including entry/exit jumps and
emulator events, with identical whole WRAM in normal and observer runs.
The four chunks save mean 263.64–274.91 master clocks per invocation; every
case improves by at least 198 clocks. This block is approximately one-third
faster. **That is not a one-third gameplay speedup.**

## Full-route rejection

Normal721 and renderer721 both complete 8,696 frames with identical entire
timelines and PCM. Different encounters prohibit using total route duration
as an equal-work speed ratio.

| Uniform two-pixel one/three-frame camera pairs | East | West |
| --- | ---: | ---: |
| Original NES | 3 | 0 |
| Parent608 | 11 | 18 |
| Fused position720 | 21 | 15 |

Actual displayed scrolling worsens eastward and improves slightly westward.
Audit722 retains all hold distributions, long stops and censored edges. The
optimization does not meet the original-speed gate.

Renderer audit723 checks 7,381 complete eligible frames without a split and
6,422 covered unchanged-camera frames without a stale hold. However, all 160
street lines are missing at fade frame2117. This remains a coverage FAIL;
the audit does not drop the frame to obtain a pass.

Room-entry audit723 measures whole loads of 21/29/29 frames against NES
20/31/30. The first load is one frame late; fixed-offset fade comparisons
also fail. Passing arithmetic and unit tests do not override these failures.

## Instruction follow-up and attribution guard

The candidate's complete instruction-observer replay723 also matches normal
execution and PCM. Audit724 retains all complete main-start/camera-store pairs
in frames7400–7465: starts at lines55–114, stores at lines18–148. This includes
interrupt time and different encounters; these ranges are not a speed ratio.
This bounded window does not contain a valid moving one/three-frame example.
It does not negate the full-route rendered cadence failures.

The diagnostic search exposed an attribution trap: camera87 was stationary
across repeated stores before movement resumed. Looking only at the selected
store frame could mislabel its already-visible image as a new publication.
`audit_pacing_case.py` now requires preceding-frame coverage and rejects a
camera already visible before its selected store. Unit tests exercise repeated
positions, same-frame/delayed visibility, missing coverage and split cameras.
The original parent counterexample was rerun as
`sprite-position-parent-counterexample-724`: producer intervals2/2 still yield
display intervals1/3. The stricter guard does not erase the known regression.
Historical report654 binds the older auditor; report724 binds the current one.

570 unit tests pass. Oracle, timing and patch-audit source hashes were checked
against the current files. No acoustic fidelity, pop-free sound, full-game
speed, new status/shop validation or hardware qualification is claimed for
this candidate. The separately qualified noise correction remains separate.

Evidence: <http://127.0.0.1:8766/sprite-position-review-724/>.
