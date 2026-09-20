# Deterministic SPC hardware replay

Follow-up: [combat timing and actual Rival scrolling](COMBAT-TIMING-PHYSICAL-SCROLL.md)
adds all-state combat loop checks and a physical movement recording.

September 18, 2026. This iteration adds an executed emulator/hardware regression
fixture, not a new game ROM. Current game remains `0956bd97b78f`.
[Review: native audio, actual hardware video, capture-frame gallery](http://127.0.0.1:8766/packet-player-review-1291/).

## Why

The prior real-game knockdown-associated audio gap has not been explained.
The focused `combat-knockdown-audio` input scenario captures an actual encounter,
pause and resume without editing game memory. Captures1224/1225 match completely
with the SPC observer enabled. Transport1228 checks2,512 packets and1,347 sweep
events. Ordered NES replay1229 executes9,346 writes. Silence comparison1230
does not reproduce a sustained unexpected gap; this is not proof that the
earlier physical-game gap was intentional.

To eliminate differing enemy encounters, `snes/apu_packet_replay.asm` loads the
exact candidate SPC engine, unchanged production sender, and all captured
23-byte packets. Empty source frames are retained. Packet delivery is scheduled
at VBlank; original game within-frame timing and CPU workload are not retained.
No copyrighted game graphics are included in this diagnostic cartridge.

## Qualification

Final fixture1257 SHA256:
`0e993a08a7250f58402b89df2e242e880d78a2e432dea5f401c6460ea8a0bdeb`.

- Normal1258 and receiver-observed1259 have byte-identical entire WAV, RAM and
  timing traces. Audit1265 verifies every one of57,776 received bytes, ordered
  indices and alternating receiver PCs across2,512 packets/2,906 source frames.
- Executed half-speed1260/1261 fails the contiguous source-frame cadence check.
  Executed wrong-data-port1262/1263 passes the CPU shadow check but fails actual
  receiver validation. Both retain failure evidence.
- Video1264 decodes the complementary16-bit marker and matches every one of
  the2,906 source frames to the same emulator frame's RAM receipt. Full WAV,
  RAM and final image remain byte-identical with this observer enabled.
- A previous diagnostic version drew its marker after the SPC handshake and
  tore the marker when VRAM writes missed VBlank. Failed1256 is retained.
  The final fixture draws before the handshake; no game code changed.

## Rival recordings

Boot1266 captures30 seconds using simultaneous pre-mute raw PCM and OBS AAC.
The immediately following recording was refused because OBS had not yet become
idle after StopRecord. Cleanup reloaded the original game. No existing recording
was stopped by that failed attempt. The coordinator now observes idle after its
owned recording, and a separate tail-only trial1278 successfully captured the
later portion of another identical replay.

- First video1276:1,787 decoded frames,1,600 valid source markers, source1–1,603.
  Pre-launch frames are retained. Duplicates/skips are reported.
- Tail video1281:1,791 decoded frames,1,675 valid markers, source1,361–2,906.
  116 markers are unreadable. Exact decoded frame250 shows a MiSTer
  “Screen saved” notification obscuring the upper marker; no repaired pixels or
  guessed frame IDs are substituted. Completion repeats are retained.
- Audio1279: fixed10ms RMS-bin offset trained on emulator seconds8.6–14.6;
  held-out correlations0.910,0.926,0.861,0.889.
- Audio1288: trained on emulator seconds25–31; held-out correlations0.922,
  0.904,0.941,0.989,0.887.
- Neither comparison finds reference-active / capture-silent runs of30ms or
  longer at the declared thresholds. Both detect an injected100ms dropout.
  The reports' `offset_samples` field is measured in **10ms envelope bins**,
  not PCM samples. Fixed offsets include capture buffering and are not game
  audio latency. Raw/AAC use independent fixed branch offsets.

These are broad audio-activity checks, **not** waveform, pitch or pop-free
certification. In particular, sub30ms clicks remain outside this gate. Native
clips retain their original samples/rates; no gain normalization, resampling,
pitch shift, or time warp is applied. Both physical audio paths share
DeckLink/OBS, and there is no physical SPC receiver trace.

## Handoff and next

Rival process19722 was observed running
`/media/fat/RCR-SNES-0956bd97b78f.mgl` after the trial. Screenshot1285 verifies
SNAC Yes;1287 verifies OSD closed and the game restored at its player-selection
screen. No gamepad gameplay input was sent during this iteration. Saved
SNES.CFG remains
`066fa49a5cb02a5e73a6caa73ea937cd2711f6b78e4cdb2099a673e9229dd933`.
OBS recording/replay are stopped, raw taps removed, routing/gain unchanged.

The controlled player narrows the investigation: these captured commands do
not cause a sustained missing-audio interval under this simpler hardware
schedule. It does not clear the game's original sub-frame delivery timing,
load-dependent stalls or short pops. Next compare short transients and the
game's exact sender placement under combat load against this deterministic
baseline. Full original-speed parity and strict graphics publication remain
open. Controller presets, splash sound and game graphics were not changed.
