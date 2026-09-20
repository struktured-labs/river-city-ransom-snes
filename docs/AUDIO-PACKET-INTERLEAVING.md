# Recording sound packets during acknowledgement waits

September 18, 2026. Diagnostic experiments only; nothing deployed and no
MiSTer, SNAC, OBS or recording state changed.

[Bound measurements, exclusions and failed fade collages](http://127.0.0.1:8766/audio-packet-interleaved-review-1588/).

Follow-up [initialization and selective-coverage controls](AUDIO-PACKET-STARTUP-CONTROLS.md)
show that startup initialization alone can reproduce the fade failure. These
earlier combined builds do not isolate runtime logging as its only cause.

## What changed

The earlier logger executes all recording work after the SPC transfer. These
two experiments instead publish each pair's port token, then copy that pair
to SRAM while the sound processor handles it, before checking acknowledgement.
Header initialization follows the command token; the final XOR check follows
the last data token. Commit/pointer advancement still follows acknowledgement.
Neither changes the SPC engine, game graphics or production cartridge.

- Interleaved1568 keeps DB on the SRAM bank and uses long port addresses and
  a local Y-bounded poller. SHA `010ba21769417d570099e3269fe3e70013308fcae9a1133d0fda6bea00b2b1c1`.
- Original-poller1577 temporarily switches DB only for SRAM accesses, then
  restores DB0 before the original `wait_port0`. SHA
  `98ed868d3c0c5316e9ebd06a3771eb22453dc8d618357a028dae6d7aaf335e93`.

Both unroll the same twelve paired transfers, preserve data-before-token
ordering, use the existing outer length gate and restore DB/DP/carry status
for the exact already-saving audio bridge. A/X/Y remain scratch. They are not
drop-in general-purpose replacements for every caller of `spc_frame`.

## Packet accuracy and executed failures

Both run 5,000-frame normal, SPC-receiver and CPU-timing captures. Within each
variant, complete WAV, final WRAM/SRAM, per-frame metadata and screenshot match
across all three observers. Each sends 4,606 independently observed packets;
all 4,095 retained records match exactly, with 511 overwritten records disclosed.

`check_packet_log_timeouts.py` injects carry-failure returns at READY, command
and all twelve data-token waits, in fourteen fresh processes on1577. Every
case produces valid committed timeout records and the outer runtime EE flag.
The readiness case retains112 records, command/first eleven data stages12
each, and final data stage111. These are deliberately failed captures, not
passing game runs. Timeout records may contain partial data or old tail bytes
and must never qualify as received packets. This tests actual error paths, not
all physical stuck-port behavior or arbitrary timing perturbations.

## Sender timing, not a net-overhead claim

| Whole sender | Median master clocks | Range | Included spans | Excluded crossings |
| --- | ---: | ---: | ---: | ---: |
| Unmodified | 24,238 | 19,280–40,812 | 3,266 | 1,302 |
| Interleaved long-port | 24,924 | 20,078–43,488 | 3,250 | 1,318 |
| Interleaved original poller | 25,064 | 20,428–43,280 | 3,262 | 1,306 |

Each retains one trailing incomplete entry. Measurements run from sender entry
through before RTS, including protocol waits and any logging. Frame crossings
and the possible NTSC short scanline are explicitly excluded rather than
assuming an incorrect constant frame length. All exclusions are in the report.
These independent runs have different timing/encounters; subtracting their
medians is **not** a matched-command measurement of logging overhead.

## Game regressions decide deployment

Normal/main/raster captures complete 8,937 frames for1568 and 8,857 for1577;
both observers are neutral within their respective builds. Stable main-loop
cadence passes 3,588 and 3,547 loops respectively across all four rooms, each
with two NMI advances and two-frame consecutive starts. Park camera checks
find no short irregular holds; long14-frame holds remain in the evidence.

Both final short-replay screenshots match the uninstrumented parent, but
their complete WAV and final WRAM do not. More importantly, both full-route
room-entry gates **fail**: first visible offsets8/6/7 versus original7/7/7,
with exact fixed-offset background differences retained. A matching final
image did not predict correct loading/fade timing. Neither is certified
timing-neutral or deployed.

Next: investigate a bounded recording interval in steady gameplay, with
explicit coverage/gap accounting and independent packet alignment. Recording
through every room load still perturbs the timing being measured. Physical
audio gaps, pop-free playback and whole-game original-speed fidelity remain
open; none of these diagnostic passes establishes them.
