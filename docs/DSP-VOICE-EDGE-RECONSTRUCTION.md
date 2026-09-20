# Actual DSP voice reconstruction at retained transients

Review: <http://127.0.0.1:8766/voice-edge-audit-2298/>.
The previous turn made progress by isolating exact-command noise/triangle stems
and qualifying the latest speed candidate's SPC delta. This turn identifies the
source of selected **replay** edges more precisely. It does not phase-match or
declare the physical pops fixed. No cartridge, Rival, controller or OBS changes.

## Fresh observer with unchanged execution

New isolated core `.deps/snes9x-voice-2292/libretro/rcr_voice_edge_libretro.so`
adds host-only reads at four actual DSP execution sites:

- Noise update: previous/current 15-bit state and flags.
- Voice source: interpolated/noise source, envelope actually used, resulting
  output, pitch, pre/post-startup delay and control snapshot before the next
  envelope update. The older V4 observer's envelope is already updated and
  cannot substitute for this sample's used envelope.
- Left/right voice mixing: signed volume, contribution and accumulator before
  mixing, for all eight voices, not just the audible four.
- Master/echo mixing: signed volumes, accumulator, echo input and output.

The selected windows are fixed by review2290's eleven replay peaks, each with
128 samples before/after. They cover2,827 complete stereo sample periods. No
window is moved in response to the new trace. The trace records all27 events
per selected DAC sample, at their exact clock phases and in order.

Fresh normal2293 and observed2294 match in complete PCM, timeline, RAM and final
image. Actual received bytes cover all1,238 packets; raw DAC equals delivered
PCM. The normal waveform also matches the earlier review's waveform byte for
byte before its sample indices are reused. Different-core controls are rejected.

`tools/snes9x-voice-edge.patch` preserves the exact source delta from the older
pitch-observer tree. Its reverse applicability was checked against the executed
tree. Build with a fresh copy of that tree, apply the patch, and **force rebuilding
objects** (`make -B -C FRESH_TREE/libretro -j4 TARGET_NAME=rcr_voice_edge`): the
makefile does not track the indirectly included `SPC_DSP.cpp` dependency. Initial
link-only output was not used; the tree was fully rebuilt, then its DSP object
was forced again after adding pre-startup delay observation. Historical cores
and their source files remain unchanged.

## Reconstructed samples, not just plausible signal plots

Audit2298 checks every selected sample:

1. All eight source and16 stereo voice stages, noise and both final mix stages
   exist exactly once at the required phases.
2. Noise either holds or performs the documented feedback recurrence; contiguous
   observations preserve its state. Noise-enabled raw samples equal the signed
   observed noise state. There are1,381 actual state transitions in these windows.
3. Every raw source multiplied by the envelope produces the observed output.
   Source flags, ADSR, GAIN, sample selection and live pitch registers agree with
   independent DSP-write timing.
4. Signed per-voice volume multiplication, sequential accumulator clipping,
   master/echo volume and final muting reconstruct native stereo PCM **exactly**.
5. Noise's isolated output independently matches the previous host-mixer stem
   at every selected sample, not just at the selected peaks.
6. Both actual pulse pitch latches reconstruct from low/high register-read
   phases, accounting for key-on startup. **Zero split-byte pitch samples** occur
   in these selected windows; this does not erase the known ones elsewhere.

One-field corruptions of actual noise, envelope, volume and final-mix records
are each rejected by the same checker. Tests additionally reject missing or
duplicate stages, wrong phases, bad source controls, wrong native DAC samples,
incomplete windows and reversed traces. The noise recurrence's full32,767-state
cycle is checked separately. This is DSP emulation observability, not an
independent proof of NES synthesis fidelity or physical FPGA implementation.

## What changed in the diagnosis

At all eleven selected replay peaks, noise volume, envelope, clock flags,
ADSR/GAIN and master volume are steady across the edge. Its sharp component is
the normal DSP noise-state transition, not a one-sample control-volume spike.
That does not establish that this SNES noise approximation sounds like NES noise.

Two substantial pulse-2 edges coincide with observed, correctly delivered
key-on startup:

| Physical review window | Replay sample | Pulse-2 observation |
| --- | --- | --- |
|12.251542s|29,875|32 SPC clocks after actual KON latch; envelope496→0, starting startup silence|
|20.274271s|286,850|192 clocks after latch; envelope0→496, pitch0→132, leaving startup silence|

Both restarts have correct initial pitch. Other selected pulse edges retain
stable controls and changing oscillator output. These associations classify
the replay mechanisms only: physical within-frame scheduling, oscillator phase
and the out-of-command-coverage event are still unresolved. No click-removal
filter, volume attenuation or missing-retrigger workaround was introduced.

Next audio work should compare these current-engine pulse-2 startup edges with
an executed NES reset reference. Earlier phase-repeatability tests establish
that suppressing resets is wrong, but do not establish exact onset/offset
waveform fidelity. Speed/scrolling work also remains open for current-cartridge
menu and physical qualification; these acoustic observations do not waive it.

## Verification

Full suite: **1,099 tests pass**, `/tmp/rcr-tests-2299.log`.
Report2298 is authoritative;2295 predates restart associations and2296 predates
independent source-control register checks. Earlier outputs are retained.
The web review links the unchanged native listening clips and fixed-scale plots
from review2290, and includes complete source/mixer snapshots and key-on context.
The rendered table/details layout was inspected in Chromium. No subjective
listening verdict or pop-free release claim is made.
