# Exact hardware-command replay: three retained audio gaps

September 18, 2026. [Waveforms and native audio comparison](http://127.0.0.1:8766/hardware-packet-gap-review-1698/).

## Finding

All 1,238 packets from physical episode1673 were replayed through the exact
diagnostic SPC engine. Independent emulator receiver instrumentation confirms
every received byte. Observer and normal runs have identical audio, timeline,
RAM and final image; raw DSP output matches delivered PCM. There are no wrong
first pitches or stale nonzero pulse onsets in this replay.

The replay produces silent intervals near all three retained physical gaps.
A **single 1.260-second offset**, fitted to 2ms RMS envelopes on replay4..7s,
gives the following results. No gap is independently aligned.

| Physical gap, fixed AAC time | Physical silence | Replay silence | Physical interval overlapping replay silence |
| --- | --- | --- | --- |
| 3.922188s | 17.625ms | 16.448ms | 93.32% |
| 4.020479s | 19.8125ms | 33.333ms | 92.51% |
| 19.917979s | 11.083ms | 31.367ms | 100% |

Each corresponding packet neighborhood includes all-channel quiet commands.
Actual replay DSP writes show zero pulse/noise volumes and triangle pitch,
with triangle GAIN `$9f` (release), despite nonzero triangle volume registers.
Checking volume registers alone would miss envelope-driven silence. These are
register observations, not internal envelope snapshots on physical hardware.

This supports **commanded rests** as an explanation for these three gaps.
They are not sufficient evidence of missing transport packets. It does not
establish sample-exact causality, explain all reported pops, or certify audio
fidelity. The previous uninstrumented production episode's 10.354ms gap is
not the same episode and is not resolved by this comparison.

## Limitations and controls

- Replay starts with cold SPC state and sends one packet per VBlank; original
  within-frame timings and prior DSP state are not restored.
- Training correlation is 0.849714. Nine fixed-offset held-out correlations
  range 0.565867–0.844222, retained individually in the report.
- Local diagnostic offset searches are retained but never applied to clips or
  gap comparisons. The ±4ms overlap sensitivity is not a confidence interval.
- Original physical raw/AAC offset remains 271,289 samples, independently
  established in the hardware trial. No amplitude matching, normalization,
  resampling or per-gap retiming is applied to audio evidence.
- All six native-rate stereo clips are exact source sample slices. All ten
  served review assets were fetched and hash-checked.
- The diagnostic logger is not timing-neutral and is not a release candidate.
  Rival's regular `777635fa6d86` cartridge was not changed or restarted here.

## Reproducibility and tests

Fixture `build/hardware-packet-replay-1691/player.sfc`:
`099f7343c6aa7b546da86f438cb4794edbb1c1f3da2dc2a00fc60f1ffff41e40`.
Normal execution1692 and qualified observation1694 are bound in review1698.

```sh
python3 -m tools.audit_hardware_replay_gaps \
  --fixture build/hardware-packet-replay-1691 \
  --normal build/hardware-packet-replay-normal-1692 \
  --observed build/hardware-packet-replay-observed-1694 \
  --hardware build/audio-packet-hardware-review-1690 \
  --out build/hardware-packet-gap-review-reproduction
python3 -m unittest discover -s tests -q
```

925 tests pass. New tests reject corrupt/incomplete packet streams and silent
alignment inputs; recover a known synthetic offset with independent held-out
data; detect an injected held-out dropout; preserve GAIN-release context; and
check fixed-scale SVG coordinates and escaped labels. The synthetic alignment
test caught floating-point bin truncation creating 95/97-sample bins instead
of exact 96-sample bins at48kHz. Nearest-sample boundaries fix this; measured
gap overlap and the fitted offset remain unchanged.

Failed observer1693 lacks the required voice hook and is not used. Analysis1695
failed for absent matplotlib; dependency-free SVG generation replaces it.
Pre-correction review1696 remains historical but no longer matches the current
analysis source hash. Review1697 has the corrected measurements but full-scale
axes make these quiet intervals difficult to see; review1698 uses the same
fixed ±0.025 full-scale display range for both sources and every gap. Audio
is unchanged. **1698 is the authoritative corrected report**. No failed
outputs were deleted or substituted into passing evidence.

Next: target audible nonzero transients and remaining rare slowdown, rather
than treating every exact-zero musical rest as transport sputtering. Original
speed, pop-free audio and release readiness remain open gates.
