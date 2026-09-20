# Mall NPC graphics: missing executed mapper writes

The mall corruption is reproduced without hardware input or RAM mutation.
`traversal-mall` extends the jump route with Left for 60 frames, Up for 180,
and 120 idle frames. This reaches room `$42=2` in both original and port.
The alley exit direction was corroborated by the
[walkthrough](https://strategywiki.org/wiki/River_City_Ransom/Defeat_Moose),
then verified by actual gameplay. Merely holding Right in the trash area
was not sufficient to establish a scrolling failure.

The read-only FCEUmm observer patch `tools/fceumm-mmc3-observer.patch`
exposes mapper registers without emulated reads or writes. Its mall replay
has all 5,872 frame records identical to the normal-core run after removing
the added mapper field, and byte-identical WAV audio. At the settled mall
checkpoint NES CHR R0–R5 are `[8,10,64,66,83,65]`; the old SNES candidate
has `[8,10,64,66,69,65]`, with no pending upload jobs. This is a missed
selection, not merely a slow upload.

FCEUX input replay in `build/reference-mall-02` records the bank-83 write
at frame 5656, PC `$FEC1`. Its execution coverage adds 464 instruction
starts, including previously uncovered `STA $8000` at `$FEBB` (physical PRG
offset `$1FEBB`) and `STA $8001` at `$FEC1` (offset `$1FEC1`). The existing
builder correctly patches both once given this trace: 208 instead of 206
hardware patches, with the same 43 shared stubs. No speculative mapper
arithmetic change is needed. Earlier builds lacking this trace remain broken.

## Reproduce the corrected candidate

```sh
python3 tools/build_native.py --experimental-fastrom \
  --trace build/reference-title-05 --trace build/reference-walk-02 \
  --trace build/reference-inventory-02 --trace build/reference-walk-long-01 \
  --trace build/reference-mall-02 --out build/mall-coverage-01
```

ROM SHA: `1f53846626076da33a1a9fdb957c920fdaf66e9674d80736cbfaf9b97a74fd18`.
The additional trace is source-ROM/hash verified by the builder, not a scan
that guesses whether ROM bytes are instructions. Traces and ROMs stay local.
To recapture coverage, `tools/capture_nes.py --replay` accepts the verified
NES benchmark directory; see its CLI for frame count and output options.

`build/mall-coverage-route-01/snes` completes 6,010 frames, reaches room 2,
has no adapter faults, and finishes with all six CHR registers matching NES
and no pending CHR jobs. Visual inspection shows intact NPCs rather than
the fragmented purple sprites in `build/mall-route-01/snes`.

`tools/check_mall_mapper.py` verifies capture hashes, delivered inputs,
completion, room and settled CHR bank selection. It creates a two-image web
collage and machine-readable result. The corrected capture passes at
`build/mall-coverage-audit-01/index.html`; running the same checker on the
old candidate fails at `build/mall-coverage-negative-01`. Three unit tests
cover stale selection, wrong room and pending uploads. All 97 unit tests pass.

The baseline replay still takes 2,074 frames, unchanged from the parent.
This is a graphics coverage correction, **not** an original-speed pass or
audio-popping fix. The compared NPC states are not pixel-identical across
NES/SNES; this audit does not claim they are. Shop interiors and full
scrolling/audio/performance remain unverified. Nothing deployed to Rivalmage.
