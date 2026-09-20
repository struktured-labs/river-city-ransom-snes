# Pulse sweep timing and executed divider regression

September 18, 2026. Diagnostic work; **no scheduler fix or ROM deployment**.
Review: <http://127.0.0.1:8766/sweep-timing-review-1081/>.

The previous experimental arithmetic correction remains candidate
`275eeddd829bb9dc119f22429488639da54ad243cee83bccb8c4f71aa751feab`.
It is not the last deployed Rival ROM (`071c89e…`). No physical input, restart,
OBS setting change, or capture was made in this investigation.

## Actual observations

Capture 1073 observes executed SPC period stores. Capture 1074 observes NES
pulse writes and before/after half-frame state while replaying candidate bus
commands using the publication-frame replay 1072. Both observers retain the
entire normal timeline and WAV byte-for-byte; NES final RAM also matches.
The audit binds all **23,189 pulse writes** in order, value and publication
frame, and checks all **8,950 actual SPC received packets**.

Audit 1076 compares each timer reload to its first pitch change, bounded by
the next timer write/reload. All 247 cases have both changes before that
boundary; zero exclusions. Raw cycles are retained alongside converted times.

| Voice | Cases | SPC minus NES delay range | Mean |
| --- | ---: | ---: | ---: |
| Pulse 1 | 24 | +5.588 to +11.302 ms | +8.580 ms |
| Pulse 2 | 223 | −7.662 to +10.650 ms | +1.663 ms |

This is not exact original-game sub-frame timing: the NES replay batches
ordered writes once per publication frame. No waveform phase fitting, sample
time warping, or claim of physical combat-stutter causation is made.

One pulse-2 case (packet 6104, source frame 6522) starts with different timer
periods. The actual NES half-frame sweeps 144 → 153 **between** `$4006` and
`$4007` writes. Writing high zero retains that swept low byte, so its following
target is 162. SPC receives the final raw register pair, reloads 144, then
sweeps to 153. The report retains this pair and its mismatch. Its narrow
classification requires exact observed before/after chaining, the proper
low/high write order, and matching raw/reconstructed periods. Removing the
actual intervening update or mutating either relevant period invalidates the
explanation. It is not classified as an arithmetic failure or silently omitted.

## Executed scheduler characterization

`tools/spc_divider_probe.inc` adds an explicitly called diagnostic entry to a
separate core, `.deps/snes9x-divider-1077/`. It runs the original `check_timers`
and `check_timers2` instructions at `$0983`/`$0AA8`, with corrected pulse-1
arithmetic, through their actual return. Hardware timer reads, period stores,
and DSP accesses are executed normally. A bounded diagnostic audio sink
receives DSP output; the first harness attempt omitted this sink and crashed,
which was corrected before any successful result was published.

`tools/check_sweep_divider.py` checks **36,864 combinations**: two voices,
eight divider settings, software accumulators 0–23, pending hardware counts
0–15, enabled/disabled/zero-shift controls, and timer reload present/absent.
All reproduce the legacy state transitions. Three mutated executable engine
variants are rejected: ignoring the reload's counter-clear, running the
disabled path, and changing a divider-table threshold. Mutations have strict
original-byte guards.

This is a **characterization pass, not an NES conformance pass**. Findings:

- Disabled or zero-shift sweeps return without consuming pending timer counts.
- Timer reload clears hardware counts but keeps the software accumulator.
- The update threshold is `3 * (P + 1)` hardware ticks. An update sets the
  accumulator to zero, discarding any excess.

The probe starts the enabled hardware timers at a fresh phase. Calls take
14–440 SPC clocks, below their 2,816-clock period. It does not test timer wrap,
multiple calls, negative sweeps, or full waveform fidelity. Report:
`build/sweep-divider-executed-1079/report.json`.

The pinned FCEUmm `FrameSoundStuff` instead advances sweep dividers on its
half-frame clock even when disabled, processes sweep-register reload flags,
and does not reset the sweep divider on a timer-low/high write. The transport
currently lacks explicit same-value sweep-register-write events and does not
transmit `$4017` frame-counter writes. A correct implementation needs those
semantics considered; merely priming a divider to fit the first pitch is not
a complete fix.

Do not casually reuse packet byte 20 / SPC `$54`: the fast duty-reset handler
already uses it as a pending KON mask and relies on its normal zeroed packet
value. Flag `$56` bit 5 also selects a legacy alternate audio branch. Any new
metadata needs an audited allocation and producer/consumer regression tests.

## Reproduction and validation

```sh
python3 -m tools.audit_sweep_timing \
  --snes build/sweep-timing-snes-1073 \
  --nes build/sweep-timing-nes-1074 --out build/FRESH-timing
python3 -m tools.check_sweep_divider \
  --core .deps/snes9x-divider-1077/libretro/rcr_divider_probe_libretro.so \
  --out build/FRESH-divider
python3 -m tools.build_sweep_timing_review \
  --timing build/FRESH-timing/report.json \
  --divider build/FRESH-divider/report.json --out build/FRESH-review
python3 -m unittest discover -s tests -q
```

The separate diagnostic core includes `tools/spc_divider_probe.inc` within
namespace SNES after opcode definitions. When changing that include, touch
the diagnostic `smp.cpp` before rebuilding; its Makefile does not track the
included file dependency. Do not overwrite normal/previous evidence cores.

**780 unit tests pass.** Review 1081 binds 29 source/artifact files and checks three
actual-data interleave mutations. It includes untouched existing candidate
checkpoint frames, and links earlier native listening clips explicitly as
earlier evidence. No new listening or hardware-improvement claim.

Next: implement and execute a continuous half-frame scheduler with explicit
sweep-write reload semantics, test enable/disable and timer writes across
clock phases, then rerun complete game timing/audio captures. Intermittent
physical combat sound, strict scrolling publication, and full-game speed
qualification remain open; the goal remains active.
