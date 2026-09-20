# Audio delivery over the complete mall/café route

The current `unchanged-bulk-01` candidate was replayed through the same
6,451-frame shop route using the optional SPC acknowledgement/bus observer.
`build/current-shop-audio-01/snes` has a timeline exactly equal to the stock
core capture `build/unchanged-bulk-shop-01/snes`, and byte-identical audio.
This observer did not change the measured run.

The complete trace contains 6,201 packets, all acknowledged in protocol
order, and no packet data/event-flag mismatch against preceding CPU writes.
Unlike the older short street baseline, this longer traversal exposes real
delivery gaps during gameplay and scene loads. Histogram of completion gaps:

| Display frames between completions | Count |
|---:|---:|
| 1 | 6161 |
| 2 | 20 |
| 5 | 7 |
| 7 | 1 |
| 8 | 1 |
| 9 | 2 |
| 11 | 4 |
| 12 | 1 |
| 30 | 2 |
| 32 | 1 |

All 20 two-frame gaps occur during rightward traversal. Later examples
include gaps 5/12/11 near raw frames 2439/2452/2463, 5/30 entering the alley
at 5770/5801, and 5/11 entering the shop at 6147/6158. These are not SPC
timeouts. Delayed game-side publication is a demonstrated remaining cadence
problem; whether any particular gap explains an audible pop is unproven.

`tools/audit_audio_gaps.py` validates the capture and both ordered traces,
cross-checks packet/ACK counts and NMI correspondence, and retains every gap
with a stereo clip and half-second context. It uses conservative review
windows, not sample-exact inferred DSP event positions. The complete WAV is
also included. Every generated clip was verified byte-for-byte against its
reported source sample range; hashes cover all clips and full audio.

Review: `build/current-shop-audio-audit-01/index.html`.
Source traces: `build/current-shop-audio-{ack,bus}.csv`.

## Hypothesis rejected before patching

Inspection of the legacy source suggested a possible envelope-loop mismatch.
NES envelopes reload their decay level to 15 when looping, as documented by
[NESdev](https://www.nesdev.org/wiki/APU_Envelope). However, the actual shop
route uses constant-volume/software envelopes on both pulses and noise after
initialization; no active hardware-envelope case was established. No engine
patch was made on that basis. The next correction should target demonstrated
game-side stalls and/or separately measured synthesis artifacts, not an
unexercised envelope path. Hardware popping and fidelity remain open.

## Follow-up: original pauses and packet ordering

The source-ROM-bound FCEUX shop trace also has audio-write gaps at scene
loads: frames 2101→2114 (13), 5630→5654 (24), and 6009→6018 (9).
This excludes `$4014`, which is OAM DMA, not an audio register. These are
write gaps, not directly comparable to SPC packet-completion intervals.
The original explicitly writes pulse volumes `$F0`, triangle `$80`, noise
`$30` before the mall gap. The current port instead retains `$F3/$F1/$81`
in its corresponding transition setup. This disproves the simple hypothesis
that identical mute values were merely waiting for publication.

The bus analyzer now separately reports disabled-channel high-timer writes
followed by channel re-enable within one packet. Final-byte equality alone
cannot certify preservation of these ordered events. In the current route,
eight channel events occur in two packets: all four channels at raw frames
2303 and 5757, published at 2307 and 5761, with final enable `$0F` and
accumulated flags `$CF`. The NES length-counter model ignores length loads
while disabled; see [NESdev's length-counter description](https://www.nesdev.org/wiki/APU_Length_Counter).
Whether these packets cause incorrect SPC output needs an isolated ordered
disable/reload/enable PCM test; no driver patch is justified yet. Pulse
phase/envelope side effects must not be erased merely by removing flags.

Result: `build/unchanged-ppu-bus-analysis.json`. New classifier controls
distinguish disabled/re-enabled events from enabled or unknown-enable
writes. All 101 unit tests pass. This is an ordering hazard report, not a
claim that all eight events are audible defects or the popping root cause.
