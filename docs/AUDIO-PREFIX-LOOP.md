# Faster audio scheduling iteration

Review: http://127.0.0.1:8766/audio-prefix-review-3734/

The boot-driven audio prefix ends after right_08, covering2579 frames instead
of9091. Parent3695 prefix3730 exactly reproduces all primary full-run fields
over this interval and every native PCM sample. The full harness's extra
image-derived waypoint_cursor is recomputed from each prefix image and compared,
not omitted. No emulated state, inputs, images or audio samples are changed.

Fresh observer3733 is neutral against that same-core prefix control. All6150
sparse sound-service events match the corresponding full trace3721 exactly.
The known frame2120 driver-return gap remains23.617058ms: shortening the route
does not remove the symptom. All complete calls and intervals remain in JSON.

Measured timings:

- Parent prefix capture7.760s; initial full-reference authentication plus capture
  and verification14.775s. This setup cost is distinct from reusable iterations.
- Fresh observed prefix7.565s; child capture/verification8.051s; wrapper including
  child exit and final trace authentication8.274s.
- Historical full observed replay3721:27.584s, replay only. These are measured
  individual runs, not a simultaneous benchmark or total-project speedup claim.

The first prefix report attempt3729 rejected tuple/list cursor serialization;
actual primary images were not different. It remains preserved. Observation3731
exposed a second harness bug: in-process DSP/DAC traces finish flushing at process
exit, after the original wrapper hashed them. It is not a valid cache. The new
finalizer runs the producer in a child, waits for successful exit, retains the
pre-exit receipt explicitly as incomplete evidence, and then authenticates final
trace files. Five focused tests pass, including changed-image-field/cursor and
malformed sound-envelope rejection. Review generation's two failed invocations
created no report before the corrected review3734.

Next trial commands (use fresh output names; no hardware deployment):

```sh
python -m tools.capture_audio_prefix --candidate build/CANDIDATE \
  --core .deps/snes9x-voice-2292/libretro/rcr_voice_edge_libretro.so \
  --out build/overflow-3526/FRESH-NORMAL
python -m tools.finalize_audio_prefix --candidate build/CANDIDATE \
  --core .deps/snes9x-voice-2292/libretro/rcr_voice_edge_libretro.so \
  --control build/overflow-3526/FRESH-NORMAL \
  --out build/overflow-3526/FRESH-OBSERVED
```

Verify these captures under `installed_prefix('right_08')`, not the complete
route's scenario. Do not use full-route qualification tools without explicit
prefix support. This loop retains known timing-fault evidence; it does not
certify full-route scrolling, heavy combat, pop-free sound or original speed.
Wider campaigns remain required after a meaningful candidate improvement.
