# Diagnostic sound-command ring

September 18, 2026. **Not deployed.** Rival remains on the balanced pitch build
`777635fa6d86`; no MiSTer, SNAC, OBS or recording state was changed in this work.

[Qualification and side-by-side screenshots](http://127.0.0.1:8766/audio-packet-logger-review-1546/).

Follow-up: [lower-cost implementations, endurance and full-route regressions](AUDIO-PACKET-LOGGER-COST.md).

## Why

The physical trial still contains a 10.354 ms raw gameplay silence. Waveform
matching alone cannot determine whether it was a musical rest or lost sound.
This experiment records the CPU's actual length-gated 23-byte packet immediately
after its bounded SPC transfer, with timeout status and native NMI counter.
It does not assert that a CPU shadow is proof of sound-processor receipt.

## Implementation

`tools/audio_packet_log.py` builds a separate diagnostic cartridge from the
hash-checked parent. Two uniquely located JSRs are redirected to a 559-byte
wrapper in verified unused ROM padding; SRAM header and cartridge checksum are
changed. The SPC engine, samples and game graphics are untouched. Production
assembly and the deployed cartridge are not modified.

The wrapper preserves accumulator including hidden B, X/Y, DB and processor
flags; it leaves DP untouched. All packet/metadata reads use explicit long
addresses, avoiding the bridge's nonzero direct page. A startup wrapper resets
the header on every boot while preserving the original upload result.

128 KiB HiROM SRAM stores a 32-byte header and 4,095 fixed 32-byte records.
Records include a 32-bit sequence, 16-bit NMI counter, timeout bit, packet,
XOR check and final commit marker. The XOR is deliberately not called a CRC:
paired corruptions can evade it. Count/pointer, sequence and marker checks also
reject missing, stale or uncommitted records. Snapshot during ring overwrite
may be rejected; physical export must establish a stable capture point.

Bank20's header slot is skipped on wrap. Old records are explicitly reported
as overwritten, never inferred to be available. NMI wraps at65,536; sequence
is separate. A 32-bit sequence wrap is outside this diagnostic's supported run.

## Executed evidence

Candidate1539: `c83eee4fd7f54de823825dddd0535f5b8d60682096acea3e6b6edec789937ecf`.

- 1541 sound observer,1543 normal core and1545 CPU event observer each ran
  5,000 frames with the same fixed walking/attack input.
- 4,606 complete packets were independently observed at SPC receiver stores.
  All4,095 retained SRAM packets match exactly;511 overwritten packets are
  disclosed and their payloads are **not** certified by the final ring.
- No native fault frames or retained timeout flags. The three captures have
  identical complete WAV, SRAM, WRAM, per-frame metadata and final screenshot.
- Actual corrupted-SRAM-byte and wrong-receiver-byte mutations are rejected.
  Unit cases cover missing/order errors, timeout flags, truncation, bank/ring
  boundaries, multiple wraps and a16-bit NMI wrap.
- 4,568 measured logging spans take3,898–4,270 master clocks, including
  refresh/events but excluding added call/return overhead. Short-line/frame
  crossings are excluded by the analyzer; none occurred in this trace.
- Parent1542 versus diagnostic1543 at frame5,000 differs in191 WRAM bytes,
  final screenshot and PCM. Therefore **not timing-neutral**. These observations
  alone do not identify the precise cause of every gameplay difference.

Failed/limited runs retained:1540 used the native smoke assertion at frame300,
before the logo finished initializing the game, and failed.1544's older
profile core produced no requested event trace and is not timing evidence.
1545 used a core exposing the requested events; its outputs match1543 exactly.

## Remaining work

Do not put this diagnostic on Rival as a normal gameplay update. Reduce and
characterize logging overhead, run the full park/room/cadence regressions, and
qualify save export plus an independent video/audio timing anchor. Only then
can physical sound gaps be compared with commands from that same run. This
experiment does not fix the remaining audible artifacts or prove original
game speed, neutral observation, or reliable MiSTer SRAM export.

Reproduction:

```sh
python3 -m tools.audio_packet_log build --parent build/balanced-pitch-1493/game --out NEW-CANDIDATE
RCR_SPC_RECEIVE_TRACE=NEW-RECEIVER.csv python3 -m tools.capture_audio_packet_log --core .deps/snes9x/libretro/rcr_dsp_latency_libretro.so --rom NEW-CANDIDATE/native-cpu.sfc --out NEW-CAPTURE --frames 5000
python3 -m unittest discover -s tests -q
```
