# Experimental sweep event transport

September 18, 2026. Component integration, **not a deployed sound fix**.
Review: <http://127.0.0.1:8766/sweep-packet-review-1092/>.

The previous turn implemented and executed the sweep-state kernel against the
NES reference. This turn implements its event-input path through real CPU
write handlers and the actual SPC paired receiver, preserving legacy key-on
behavior. The continuous clock and DSP pitch path are still pending.

## CPU side

`snes/sweep_events.inc` supplies `sweep_track_write`, compiled only under
`EXPERIMENTAL_SWEEP_EVENTS`. Hooks exist in the generic APU dispatcher,
direct dynamic APU path, and fused sound-commit path. The normal ROM builder
does **not** define or expose this intermediate option. Default code paths
are unchanged. The audio publication bridge clears the metadata alongside
legacy flags when the experimental define is enabled.

The helper requires A8/X8, the just-written register in X, the raw register
image already stored, and hardware NMI masked. It preserves X/Y/DP/DB and
clobbers A/flags; surrounding production paths already save their caller ABI.
Suppressed music must not generate an event. DMA and controller writes retain
their existing separate dispatch and do not write audio metadata.

Packet byte 20 (`$0A14`, received at SPC `$54`) carries:

| Bit | Meaning |
| --- | --- |
| 0 | `$4001` sweep-control write |
| 1 | `$4005` sweep-control write |
| 2 | `$4002` timer-low write |
| 3 | `$4003` timer-high write |
| 4 | `$4006` timer-low write |
| 5 | `$4007` timer-high write |
| 6 | `$4017` frame-counter write |
| 7 | Last `$4017` mode bit |

Repeated same-value sweep writes still set an event. Multiple frame-counter
writes retain the last mode while preserving pending pulse events. This is a
batched event-presence mask, not a timestamped lossless command stream. It
cannot preserve arbitrary order/multiplicity or a half-frame occurring between
two writes within one packet. Do not describe it as original-cycle-equivalent.

## SPC receiver and ownership

`tools/build_sweep_packet.py` builds an adapter after the 304-byte kernel,
relocated to `$307F` after the pinned paired/fast-reset engine. `attach()`
checks the receiver's existing tail jump, then redirects it through a
CALL-adapter/JMP-fast-reset bridge. Packet length and handshake tokens stay
unchanged. The source image is a diagnostic intermediate, not a playable
engine: its old timer/pitch routines are intentionally not yet replaced.

The adapter sets reload flags only on actual sweep-control events and updates
only each written live timer byte. `$4017` mode/reset is staged at `$9A/$9B`
for the future clock service. Most importantly, it **clears `$54` before the
existing fast-reset handler** reuses that address as its pending KON mask.
Legacy flags in `$56`, including its alternate audio bit 5, are untouched.

## Executed checks

Producer proof `build/sweep-producer-1090/report.json`:

- **6,144** generic/direct cases, all byte values and accelerated/fallback
  addresses, checking the actual 65C816 ABI, complete packet and length latch.
- **4,096** fused sound-commit cases, eight representative values, all 32
  shadow slots, all music/effect channels and suppressed/unsuppressed music.
- Two actual instruction mutations caught: omitted event hook and wrong
  register supplied to the hook.

Receiver proof `build/sweep-packet-executed-1091/report.json`:

- **57,344** combinations: all metadata bytes, seven legacy flag patterns,
  all low-four-bit channel-enable masks, and changed/unchanged duties.
- **1,024** additional delayed-sender cases: every metadata byte at four
  inter-group delays, up to 2,048 SPC clocks.
- The diagnostic host supplies CPU-side ports, but the actual paired SPC
  instructions must consume every byte and acknowledge each group. Receiving
  slots are poisoned beforehand. The unused final second port is also
  nonzero to detect accidental extra-byte consumption.
- The adapter, existing fast-reset code and existing duty-key-on helpers all
  execute. Every untargeted direct-page byte and X=23 are checked. Actual DSP
  KON writes are captured, not inferred from final packet flags.
- Four executed mutants caught: leaving metadata in `$54`, losing a sweep
  reload, using the wrong timer-high source, and dropping a receiver store.
  Leaving metadata uncleared actually suppresses the later duty key-ons in
  the observed failing case; this proves the regression gate sees that hazard.
- Receiver plus adapter takes 574–715 SPC instruction clocks without injected
  sender delays. This is not full synthesis cost or game latency.

The review revalidates source hashes and all 36 successful CPU fixtures'
ROM/receipt/RAM hashes. It does not publish a new game screenshot or imply a
new listening capture. **788 unit tests pass**, and `git diff --check` passes.

Earlier producer 1087 and directly seeded SPC proof 1089 are superseded by
the new source-bound producer and actual receiver proofs. No hardware
interaction, ROM deployment, or OBS change this turn.

## Next work

Implement the continuous frame clock and staged `$4017` handling, then DSP
period/mute publication. Check [NESdev's frame-counter reference](https://www.nesdev.org/wiki/APU_Frame_Counter)
against the local FCEUmm implementation: its quarter-step model must not be
assumed to establish exact hardware reset phase. The
[sweep reference](https://www.nesdev.org/wiki/APU_Sweep) also requires muting
based on the live target even when sweep updates are disabled.

Only enable a combined experimental game build after those pieces execute
together. Then rerun speed/scrolling/main-loop and full audio tests, followed
by raw physical audio verification. No physical combat-stutter resolution is
claimed; the full goal remains active.
