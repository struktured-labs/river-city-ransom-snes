# Executed disable/reload/re-enable counterexample

Two asset-free diagnostics isolate an ordered register sequence observed
in the game traces. They are not a claim that every reported pop has this
cause, and do not patch the production engine yet.

`tools/check_nes_disabled_reload.py` builds an original NES NROM diagnostic
from `snes/nes_disabled_reload.asm`. With a sustained pulse playing, frame
120 writes `$4015=0`, `$4003=0`, then `$4015=1`; frame 180 performs a valid
`$4003` reload while enabled. Actual `$4015` reads confirm zero length status
through phase 1 and active length after the valid reload. Frame 240 doubles
pitch. All phases execute on the normal FCEUmm core.

`tools/check_audio.py --disabled-reload` sends the current packetizer's
collapsed result at frame 120: final enable 1 plus accumulated flags `$41`.
It deliberately models the packet, not an ordered NES replay or a call
through the native adapter. Its pulse continues sounding through phase 1,
at stereo AC RMS about 1,914, failing the existing silence gate. Other tone,
restart and pitch phases pass. Result/audio: `build/disabled-reload-01`.

The NES reference at `build/nes-disabled-reload-03` passes. Its analog-filter
tail is retained, not hidden: the 100-ms-trimmed measurement initially fails
strict silence (RMS 13.53); at 300 ms the same threshold passes (RMS 0.18),
and after 400 ms samples are exactly zero. Length status was already zero.
Both measurements and exact sample windows are in the report. Full WAVs
remain available. Different cores' output amplitudes are not normalized or
claimed to be directly equivalent.

The ordinary SPC pulse regression still passes at
`build/disabled-reload-pulse-regression-01`. All 101 existing unit tests pass.
This establishes a synthesis difference for collapsed event ordering, not
merely mismatched final bytes. A correction must preserve length eligibility
separately from phase/envelope reset side effects; dropping all reset flags
on disabled writes would lose valid NES behavior. No production engine
change or Rivalmage deployment.
