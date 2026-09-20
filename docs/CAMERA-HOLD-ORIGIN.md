# Camera holds versus missing main work

No ROM change or hardware reset. New diagnostic
`tools/audit_camera_hold_origin.py` joins authenticated original-NES exact-PC
main starts/camera stores to every actual rendered camera position. It retains
all six equal-signed one-pixel endpoint holds, including those outside the
main observer window. Previously stale source bindings were refreshed by
rerunning the actual auditors on existing captures, not editing old hashes.

At rendered frames7926–7930, the original NES holds camera475 for four frames.
Main starts7924/7926/7928 commit cameras475/475/476 at7925/7927/7929. Every
commit is visible the following frame. Thus this specific hold is a repeated
game command with regular two-frame main work, not missing execution. The
diagnostic does not infer a knockback/collision cause or waive SNES holds.

Fresh reports865/866 authenticate738 main iterations and complete rendered
park sequences. Report867 checks the above relationship and retains every
other one-pixel case. Six unit tests include injected missing work, an
unpublished intermediate camera, missing boundary coverage, changed derived
data and duplicate main events. Full Python suite:652 pass.

For actual Rival footage, exact decoded frames608/610/612 and864/866/868 from
park-sweep856 were extracted without interpolation or frame-rate conversion.
Their PNG RGB data matches independent decoding exactly; hashes and indices
are in `build/main-phase-hold-context-869.json`.

- First hold: characters visibly move from608 to610 while the skyline holds;
  this is not a duplicate of the whole gameplay picture. The actor-containing
  band has20,257 pixels changing by>16 channel levels, versus84 skyline pixels.
- Second hold:864/866 are visually nearly unchanged, with131 actor-band and59
  skyline pixels above the same threshold. Lossy encoding affects pixels;
  these counts do not establish a frozen main loop or capture duplication.

Both physical events remain unmatched to exact game-state/CPU timing. The
NES counterexample is not permission to dismiss them. Existing strict gates
and audio-onset/pop questions remain open. No new Rival input, OBS changes,
ROM deployment or assertion of the current live screen was made this turn.

Review: <http://127.0.0.1:8766/main-phase-hold-origin-review-870/>.
