# Short silence discrepancies: reference filter memory versus note delivery

September18, 2026. ROM071c89e unchanged. No Rival inputs, restart or OBS changes.
The previous goal turn made progress by validating the actual SPC/DSP/DAC clock
and separating callback-boundary cases. This follow-up explains the reference
signal in the remaining short contexts, without changing the target behavior or
claiming the speed/scrolling/audio objective complete.

Review: <http://127.0.0.1:8766/triangle-game-filter-review-969/>.

## What changed in our understanding

Report957 found257 NES-active callbacks inside256 SNES exact-zero gaps. The new
filter observer965 measures the NES signal before and after its existing filter.
It preserves replay952's complete timeline, final RAM and WAV byte-for-byte.
Report966 independently reconstructs all7,144,636 integer filter outputs and
checks all8,946 filter-block starting states. Both delivered stereo channels
exactly equal the observed filter output; no waveform fit or audio processing.

| Reference observation | Same receipt/publication callback | Receipt in next callback |
| --- | ---: | ---: |
| Constant pre-filter input | 244 | 1 |
| Varying pre-filter input | 0 | 12 |

All245 constant-input callbacks have changing output because of the measured
filter state. This is not a continuing oscillation at the filter's input. The
12 varying-input callbacks are exactly the12 packet/audio-boundary cases from
audit963: NES source frame equals packet publication label, but SPC receipt
occurs in the next audio callback. Their receipt-to-first-nonzero intervals are
353–672 SPC cycles. The broader256-context range is336–676 cycles.

All244 contexts previously unexplained by the callback-boundary observation
have constant-input reference activity. One of the12 boundary contexts contains
two active reference callbacks:6502 is a filter tail,6503 is a changing signal.
That explains the257-callback versus256-context count.

### Strongest constant-input example

Frame1826: all799 pre-filter samples equal0. Output changes from910 to−448;
AC RMS384.7181949. The review plots every sample at its original position and
provides unchanged native-rate NES/SNES clips for source frames1810–1840. This
example is deliberately selected for strongest constant-input reference AC,
not as a representative score. Listening clip967 preserves different native
sample rates and amplitudes; no time/phase/gain alignment is applied.

## Scope and remaining work

These257 observations no longer support a dropped-note inference: they have
measured filter-state or callback-boundary explanations. This does **not** prove
the SNES filter/cutoff response is faithful. Filter tails are an audible part of
the reference; we have not established that all audible differences are desirable
or harmless. The replay also retains its known intra-frame write retiming.

The three147–151ms physical combat gaps and strongest physical sample-step events
remain unclassified. Those are now the priority for reproducible hardware/game
event correlation. Original-speed parity, full-game scrolling, strict publication
and input-latency validation remain open. No new user test build is warranted
by an observer-only change; Rival was left undisturbed.

## Harness and reproduction

`tools/fceumm-filter-observer.patch` adds host-only hooks to the **current local
FCEUmm tree**, not pristine upstream. It depends on the existing rounded integer
filter implementation; the patch reverse-check passes. The separate observer
binary leaves `.deps/fceumm/fceumm_libretro.so` unchanged.

```sh
make -C .deps/fceumm -j4 TARGET=rcr_filter_libretro.so
python3 -m tools.capture_nes_filter --replay build/triangle-game-nes-replay-952 --core .deps/fceumm/rcr_filter_libretro.so --out build/FRESH-filter
python3 -m tools.audit_nes_filter --capture build/FRESH-filter --silence build/triangle-game-reference-silence-957/report.json --latency build/triangle-game-dsp-latency-audit-963/report.json --out build/FRESH-filter-audit
```

Fresh processes and output paths are required. If only the included observer
changes, force `make -B src/filter.o` before linking; the dependency rules do not
track the included observer. Capture965 binds the actual filter/sound sources,
observer, core binary, player, stimulus, baseline and new timeline/audio/RAM.

Seven new tests require exact recurrence and PCM identity, retain a real
constant-input tail, and reject a one-sample input change, shifted/scaled/dead-
channel PCM, wrong filter states/coefficients, enabled lowpass, coverage gaps,
and invalid windows. One changed input sample prevents constant-input
classification even if it is tiny: there is no amplitude threshold for that
distinction. **690 tests pass**, as does `git diff --check`.

Review968 is a preliminary rendering with an imprecisely worded range; use969,
which explicitly attributes336–676 cycles to the full256-context population.
