# Preserve disabled length-load ordering across SPC packets

The native adapter now keeps an eligibility latch at WRAM `$1CA1`:
writing `$4015` clears eligibility for disabled channels; a high timer write
sets eligibility only if that channel is enabled at that instant. All
phase/envelope reset and sweep reload flags are still accumulated as before.
At publication the four tone/noise enable bits are intersected with this
latch, preserving upper/DMC bits. The raw `$4015` shadow is restored after
the send; carry still reports any SPC timeout. This is not a CPU-side length
countdown or full APU implementation. SPC expiry behavior remains separate.

`snes/apu_length_gate.inc` supplies shared logic for the native adapter and
the isolated diagnostic. Executed native case 25 checks disable, disabled
reloads, re-enable, enabled reloads and selective disable for all four
channels. It also requires reset flags `$CF` after disabled writes. A mutant
that grants eligibility during disabled writes fails case 25. All adapter
checks and 101 unit tests pass.

The isolated test from [disabled reload investigation](DISABLED-RELOAD-AUDIO.md)
now passes with `tools/check_audio.py --disabled-reload --length-gate`:
`build/length-gate-audio-01/index.html`. Phase 1 stereo AC RMS is exactly
zero, versus approximately 1,914 without the gate. Initial tone, valid
restart and later pitch change remain audible and pass frequency/activity
checks. This uses an unchanged SPC binary and preserves reset flags.

Native candidate `build/length-gate-01/native-cpu.sfc` SHA:
`9291077b107224fe61ea950860a2c567a26ac6eebbcf850b22556255693207e3`.
The complete shop route takes 6,433 frames and still matches all 17,380 café
menu pixels: `build/length-gate-shop-audit-01/index.html`. Baseline capture
`build/length-gate-quality-01/snes` completes 2,049 frames. Changed timing is
not evidence that original speed has been reached.

## Remaining verification

The old bus analyzer's default last-byte equality rule for `$4015` is no
longer the correct oracle for this candidate's deliberately gated packet.
It needs an explicit eligibility-aware mode and fresh game bus/ACK evidence;
do not silently loosen checks or reuse previous packet-pass claims. The
isolated PCM test is not a proof that every in-game pop is fixed. Sustained
game audio, transitions, speed, all scrolling and physical capture remain
open. No Rivalmage deployment.

## Full-route verification

The explicit `--length-gate` mode in the bus analyzer now independently
replays ordered CPU writes. It preserves the default legacy oracle, checks
every final enable byte against eligibility, and still checks all other
registers and accumulated flags. Controls reject an ungated packet, preserve
the DMC bit, and test valid/selective reloads. All 103 unit tests pass.

`build/length-gate-observed-01/snes` is byte-identical in both timeline and
WAV to the normal-core shop run. Its 6,190 packets have no value/flag mismatch
and all acknowledgements are ordered and complete. 413 packets require a
different enable value from the raw shadow: 384 map `$0F→00`, 23 map
`$0F→0E`, and six map `$0F→0C`. Three unflushed tail writes remain reported
by the audit rather than silently discarded.

The important PCM check is the long mall-load gap. With a fixed interior
window five frames after the previous completion and two before the next:

- Parent raw-frame gap 5762→5793: sample window 3074470..3087264,
  stereo AC RMS 1181.29 and peak 2882.
- Corrected raw-frame gap 5756→5786: sample window 3071271..3083533,
  stereo AC RMS and absolute peak both zero.

These are explicit corresponding scene-load gaps, not waveform-aligned
captures. The correction removes the unwanted held sound in this measured
interior; the complete PCM remains available including edges and other
differences. Review `build/length-gate-audio-audit-02/index.html` and
`build/length-gate-parent-audit-01/index.html`. The audit emits source sample
ranges and interior PCM metrics for every sufficiently long gap.

Delivery still stalls (24 two-frame gaps and long load gaps in this run).
This fixes demonstrated stale sound during a load, not full audio cadence,
every pop, or original gameplay speed. No hardware deployment.
