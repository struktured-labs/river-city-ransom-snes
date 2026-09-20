# Actual SPC receipt, DSP writes, and sound output

September 18, 2026. ROM071c89e unchanged; no hardware inputs or restart. The
speed, scrolling, and audio goal remains open. Review:
<http://127.0.0.1:8766/triangle-game-dsp-review-964/>.

## Result

The full 8,934-frame observer capture961 has exactly the same timeline and WAV
as normal control891. Every one of4,762,867 raw stereo DAC frames equals the
delivered PCM, without fitted offsets, normalization or resampling. All277,667
DSP register writes satisfy the DSP-phase clock equation. All8,934 callbacks
are contiguous, with no queued output backlog. Provenance962 verifies8,481
received packets against actual SPC stores, with187–1,224-cycle processing.

The diagnostic adds host logging only: no emulated cycles, synchronization,
memory changes, or audio changes. Raw DAC sample k is emitted at completed SPC
tick `32*k+28`. For every DSP write, `tick = 32*(sample_count-(phase>=28))+phase`.
For packet/ready observations, the pending DSP clock is explicitly retained;
all17,010 observations satisfy `sample_count = (tick-pending+4)//32`.

465 packets have publication-frame labels one earlier than the DAC callback
containing receipt;8,016 have matching labels. These labels are not interchangeable
clocks. Of256 short reference-gap contexts from report957,12 have this boundary
crossing and244 do not. All256 observed first-nonzero samples follow their nearest
preceding received packet by336–676 SPC cycles, approximately0.33–0.66ms at the
nominal32,040Hz DAC rate. This is contextual association, not attribution of
every onset to a particular voice or proof of NES synthesis fidelity.

### Concrete frame6580 example

| Event | Exact observation |
| --- | --- |
| Delivered callback6580 | Samples3,507,365 through3,507,897 inclusive |
| Packet6162 publication label | Frame6580 |
| Last packet byte received | SPC tick112,254,164 |
| First possible DAC sample after receipt | 3,507,942, in callback6581 |
| DSP key-on `$4C = $03` | Tick112,254,268 |
| First nonzero sample | 3,507,953, tick112,254,524 |
| Receipt→first sound | 360 cycles, nominal0.351ms |

The silent callback6580 ended before this packet arrived. It is not evidence of
a frame-long SPC receive-to-sound stall. Native-rate NES/SNES clips remain
available in review960; no audio has been altered to make the comparison fit.

## What remains unresolved

The other244 short-gap contexts are **not explained by this callback-boundary
finding**. Of257 NES-active interior callbacks across the256 contexts,250 are
one frame after the gap begins,5 are two frames after,1 three frames after, and
1 seventy-nine frames after. Cutoff timing, NES filter decay and APU behavior
need separate investigation; this distribution alone does not classify them.

The three147–151ms physical combat gaps in recording941 still have no correlated
hardware APU trace. No pop-free, original-speed, controller-preset, or release
claim follows from these results. Rival's last verified state remains paused
outside Cross-Town High with SNAC Yes; it was not re-inspected or changed here.

## Reproduction and regression controls

`tools/snes9x-dsp-latency.patch` records the observer hooks relative to the existing
SPC packet/receive-instrumented dependency tree, **not pristine upstream Snes9x**.
The added implementation is `tools/snes9x_dsp_latency.inc`. The patch reverse-check
passes against the current tree. Capture961 binds the actual four modified source
files, resampler, wrapper, core binary, ROM, timeline, WAV and all six traces.
Preserve the normal and span-observer binaries when rebuilding this variant.

The dependency make rules do not reliably notice included DSP/SMP source edits.
Force those objects; also force apu.o when changing the callback hook:

```sh
make -C .deps/snes9x/libretro -B -j2 ../apu/apu.o ../apu/bapu/dsp/sdsp.o ../apu/bapu/smp/smp.o
make -C .deps/snes9x/libretro -j4 TARGET=rcr_dsp_latency_libretro.so
```

Use fresh output paths for each command:

```sh
python3 -m tools.capture_dsp_latency --core .deps/snes9x/libretro/rcr_dsp_latency_libretro.so --rom build/triangle-game-inplace-branded-890/native-cpu.sfc --out build/FRESH-capture
python3 -m tools.audit_spc_event_provenance --capture build/FRESH-capture --normal build/triangle-game-inplace-normal-891 --keyons build/FRESH-capture-keyon.csv --synth build/FRESH-capture-synth.csv --bus build/FRESH-capture-bus.csv --received build/FRESH-capture-received.csv --out build/FRESH-provenance
python3 -m tools.audit_dsp_latency --capture build/FRESH-capture --normal build/triangle-game-inplace-normal-891 --provenance build/FRESH-provenance --silence build/triangle-game-reference-silence-957/report.json --out build/FRESH-audit
```

Review964 is a source-bound presentation of specific retained audit963, including
all256 contexts; its example deliberately points at capture961. Six clock/PCM
unit tests reject shifted, gain-modified or truncated raw PCM, invalid phase,
missing packets, invalid registers and callback backlog/gaps. Four presentation
tests require neutrality, preserve the12/244 distinction and reject inconsistent
latencies/labels or empty evidence. The full suite has683 passing tests.
