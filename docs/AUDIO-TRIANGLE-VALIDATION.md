# Triangle missing from the right output

The sustained menu comparison suggested a weak triangle component in the
stereo-average signal. An isolated triangle probe then demonstrated the actual
defect: active-tone RMS was about 1,127 on the left and exactly zero on the
right. The explicit channel-disable phase correctly silenced both outputs.
This was not an acknowledgement failure or a pitch failure.

## Checked correction

The pinned legacy engine's mono-triangle branch at SPC $0686 contains:

```asm
MOV $F2,#$20
MOV $F3,#$7F
MOV $F3,#$21 ; wrong port: changes left volume, does not select right volume
MOV $F3,#$7F
```

`tools/prepare_audio.py` changes the third instruction to `MOV $F2,#$21`.
This is the operand at binary offset $028E: $F3 → $F2. Instruction size and
timing are unchanged. The DSP's address/data ports and voice left/right volume
registers are documented in the [SPC programming reference](https://snesmusic.org/files/spc700_documentation.html).

The tool checks the entire pinned source SHA and the local instruction
preimage, writes a separate build artifact, and leaves the third-party source
binary untouched. Both the production builder and audio diagnostic use this
same correction. The production manifest records original and corrected engine
hashes, patch offset, and patch-tool source hash.

- Original engine SHA: `4e0951342dc2cf3ccc5caf1854e8cf7136aafa5d2ee137ea86c0b287b18a0f22`
- Corrected engine SHA: `cb1202386613ed3d8f1a27c6394702469b318050d08125588fbd89b200bc681e`
- Candidate `build/triangle-mono-01/native-cpu.sfc` SHA: `727f7083265524cb7e0b79d4cc4bd429caae935a6cf81eeeaff60a36b9456614`

## Executed evidence

```sh
python3 tools/check_audio.py --core /tmp/rcr-snes9x/libretro/snes9x_libretro.so \
  --out build/triangle-fixed-02 --triangle
```

The probe runs a sustained ~220 Hz triangle, explicit disable, restart, and
~440 Hz pitch change. WRAM telemetry verifies triangle control, timer and enable
registers against the scheduled frame. Both outputs must pass the existing
pitch, activity, clipping and near-zero-run criteria. All four phases pass.
The nested unpatched-engine run must reproduce the specific left-only defect;
dead output on both channels or a failed mute cannot satisfy that control.

`build/triangle-fixed-02/index.html` provides both complete WAVs and per-phase
left/right RMS for audit. This is a controlled triangle test, not a full
NES audio equivalence verdict. CI now runs it with its unpatched negative.
The standard pulse and sweep-reload profiles also pass, including the sweep's
specific missing-reload negative. All 75 unit tests pass.

The updated game's no-input menu capture is `build/triangle-menu-01/snes`.
All 2,010 frames match the prior `build/menu-audio-01/snes` for video hashes,
original RAM hashes, NMI count, phase, native CPU telemetry and delivered input.
Audio changes as expected. No graphics or gameplay timing change was intended.
This does not fix the outstanding speed/scrolling defects or establish that
all reported sputtering is gone. No Rival deployment was made.
