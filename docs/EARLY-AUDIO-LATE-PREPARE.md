# Retained-NMI audio and late graphics preparation

Candidate `build/late-prepare-on-294/native-cpu.sfc`, SHA-256
`e9fe3c329c7d7082cc2b6dd2302332091734a636754d204254bd077276557fec`,
is **not deployed**. It passes the scoped park cadence gate, not whole-game
speed or complete audible-fidelity acceptance.

## Cause and implementation

The camera-edge fix alone (286) left 15 stable park packet intervals over
536,049 master clocks (1.5 nominal frames). Servicing sound earlier in a
retained NMI reduces this to three (290), but the worst becomes 747,138 clocks.
The instruction trace `early-audio-trace-293` shows why: camera work returns
at raw frame 9321 line 233; row preparation, palette, sprites and CHR staging
then cross the next VBlank edge. The following interrupt is lost while this
work is still protected. This is a CPU scheduling failure, not an SPC mailbox
acknowledgement stall.

Two default-off build options address the measured path:

- `experimental_early_deferred_audio` requires the retained/deferred game-NMI
  scheduler. After its existing late-VBlank phase wait, the fixed `$5F00`
  bridge calls the original `$FA54` sound driver, restores bank mapping through
  `$FF29`, and publishes that newly computed packet. It preserves caller
  registers, status, stack, direct page, data bank and mapper scratch. It does
  not replay old packets or insert silence. Running before the phase wait
  would risk accidentally waiting another frame after sound crosses wrap.
- A marker in `$1CFD..$1CFF` records the complete 16-bit NMI event ID. The later
  return skips sound only for that exact event. A stale marker is consumed but
  does not suppress a new event, including low-byte collisions and wrap.
- `experimental_late_prepare_guard` requires early sound. Only the already
  serviced retained-NMI return checks the actual nine-bit beam position.
  Visible graphics preparation is deferred at line 140 or later. No staging,
  dirty flags or ownership are retired on deferral; the next producer still
  has the work. Normal returns and hidden transitions retain their path.
  Line 140 is a conservative tested policy, **not a universal worst-case
  execution-time proof** for every room/workload.

`EARLY_AUDIO` is an optional linker segment replicated at the same address in
all game banks. Default-off controls 290 and 294 are byte-identical to their
respective parents; the latter also verifies the shared marker-macro refactor.

## Executed helper tests

- `early-audio-oracle-293`: production bridge with real bank switching,
  synthetic sound endpoints, caller-state checks and 24 event-ID cases.
  Duplicate sound calls, omitted bank restore, wrong saved high byte and
  ignored high-byte comparison are all rejected.
- `late-prepare-oracle-295`: production cutoff helper at lines
  10/139/140/200/250/260 in three transition states (18 cases), with stack,
  register and poisoned staging/dirty-state checks. A late cutoff, ignored
  vertical high bit and hidden-state policy leakage are rejected.

## Exact candidate integration

| Evidence directory under `build/` | Result and limit |
| --- | --- |
| `late-prepare-park-audit-295` | Full 9,410-frame input-only route; zero stable unpaused park packet intervals over 1.5 frames; no native faults. |
| `late-prepare-neutral-spans-296` | Zero late NMI-entry intervals in observed frames 7550–9390; complete timeline and PCM identical to normal core. |
| `late-prepare-scroll-sweep-296` | 526 common camera positions, zero scenery-band mismatches and late scroll publications; **overall FAIL** because room 3 has 63 samples, below the unchanged minimum 64. |
| `late-prepare-entry-audit-295` | First scenery 9/8/9 versus NES 7/7/7. Whole room-change-to-visible 26/31/31 versus 20/31/30. Strict timing and fixed-offset fade gates **FAIL**. |
| `late-prepare-status-audit-298` | Both Present Status entries match NES with zero mismatching pixels. |
| `late-prepare-movement-audit-298` | All 32 position samples equal NES; 21 pixels traveled by each. Not full combat-speed parity. |
| `late-prepare-audio-audit-296` | 9,198 packets, one per completed NMI, zero byte mismatches or unflushed CPU writes. Full PCM and contextual clips retain transition gaps. |
| `late-prepare-phase-audio-296` | Unmodified NES/SNES park-run PCM and end screenshots for review; no gain or time fitting. |
| `late-prepare-transients-298` | Continuous positive audio callbacks across 9,410 frames, no clipping; maximum PCM step/full-scale 0.139618 against existing NES-derived limit 0.171656. Full-scale spike and missing-callback controls rejected. |
| `late-prepare-keyon-provenance-299` | Complete replay neutrality and every key-on packet field cross-checked against actual complete transport trace. |

The digital transient gate bounds sample discontinuities; it does not establish
psychoacoustic fidelity, analog output, sample-exact DSP key-on timing, or that
every listener will hear no popping. The old physical boot-ident pass is not
physical evidence for this new gameplay candidate.

## Trace provenance and an older observer limitation

The older key-on core writes only even-index packet bytes into its bus trace.
The strict full-bus parser correctly rejects that incomplete trace. No missing
bytes were fabricated and no parser requirement was relaxed.

`tools/audit_keyon_provenance.py` verifies the key-on observer, modern complete
bus observer and normal replay have identical full timelines and PCM, the same
ROM and input scenario, and fault-free completed captures. Both bus traces have
capture-time SHA-256 receipts. The old trace must equal the exact even-byte
projection of the independently captured full trace, including all CPU writes.
Every key-on packet's reset, enable and two pulse controls must equal bytes
22/21/0/4 of its corresponding full packet; all 9,198 match. The key-on trace
is post-capture cross-correlated, not retrospectively claimed to have a
contemporaneous receipt binding.

The complete trace is `late-prepare-audio-295-bus.csv`; the old observer is
`late-prepare-keyon-297`. The transient audit uses the real complete trace.
`audit_audio_gaps.py` now requires both ACK and bus capture-time hashes; older
unbound captures must be replayed, not given backdated receipts.

Reproduce provenance:

```sh
python3 -m tools.audit_keyon_provenance \
  --observer build/late-prepare-keyon-297 \
  --full-capture build/late-prepare-audio-295 \
  --normal build/late-prepare-normal-295 \
  --partial-bus build/late-prepare-keyon-297-bus.csv \
  --full-bus build/late-prepare-audio-295-bus.csv \
  --keyons build/late-prepare-keyon-297-keyon.csv \
  --out build/late-prepare-keyon-provenance-fresh
```

Next: remaining load/fade latency, sufficient dense scrolling coverage,
exact-candidate café/pause integration and physical gameplay audio. Rival
remains on branded `765052c`; controller presets remain disabled there.
