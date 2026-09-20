# Opt-in paired audio in the game

`build_native.py --experimental-paired-audio` selects the tested paired SPC
image and compiles its matching sender with `AUDIO_PAIR=1`. The engine-size
assertion requires $2C1F. Without the flag, source engine preparation, sender,
and $2C00 size assertion remain unchanged. Runtime bridge addresses continue
to come from boot linker symbols, including shifted addresses.

Candidate `build/paired-game-01/native-cpu.sfc`, SHA256
`c06511b87e82b8daf184b9016e14b86396aa90588033d2ec89467b553208ae21`.
Built with FastROM and all six retained reference traces; 242 patches and
44 stubs. No experimental raster worker enabled.

## Executed results

- Baseline 1945 frames versus retained default 1949; long route 7541 versus
  7545. Street transition 467 versus default 471 and NES 459.
- Settings/story remain 56/57 versus NES 53/54: both fail the existing gate.
  `build/paired-game-quality-01` remains failed, not release-ready.
- Room sequence 0,1,2,3 and café menu/CHR audits pass. Stationary room-3
  strip matches all 20480 pixels. Moving-camera mismatches remain exactly
  4152, 3908, 3881 pixels at the three tested checkpoints.
- All 169142 bytes in 7354 audio packets match actual SPC receive stores.
  Ordered CPU-write/length-eligibility audit has zero mismatches and zero
  unflushed writes. All packet ACK sequences pass without timeouts.
- Actual-clock transfer data phase: all 7354 packets measured, minimum
  13432, maximum 13722, mean 13600.3647 master clocks. This is not a matched
  single-byte gameplay timing comparison or full synthesis/call timing.
- ACK completion still has multi-frame gaps (including transition gaps);
  no claim of regular audio publication or eliminated popping.
- Observer capture full WAV and timeline match normal-core capture exactly.
- All 138 Python tests pass. A fresh default build reproduces retained ROM
  SHA256 `5e9a9346387b97a67ce2e94589ef76ebf14e4aa52672d7877d41578952b1d1d4`.

Evidence prefixes: `build/paired-game-{baseline,long,quality,shop,route,
static,moving}-01`; observed capture `build/paired-game-observed-02/snes`;
`paired-game-{bus,ack,receive}-02.csv` and corresponding JSON audits. The
earlier observed-01 capture omitted the bus environment variable and is not
the receiver-audit source.

This is a measured four-frame improvement and verified transport, not a fix
for scrolling or perceptual sound fidelity. Keep opt-in pending broader
gameplay/sound checks. Default and Rival remain unchanged.
