# Post-load scheduling: exact boundary and checkpoint qualification

Timing review: <http://127.0.0.1:8766/shift-fade-schedule-1964/>
Checkpoint review: <http://127.0.0.1:8766/shift-checkpoint-review-1969/>

Follow-up: [active-loop scheduling](ACTIVE-HIDDEN-BUDGET.md) now qualifies
fresh-process and guarded constant-budget replay, and restores uninterrupted
room-entry graphics with a narrower conditional cap. The results below remain
the historical checkpoint; their source reports have not been rewritten.

No Rival/OBS change, deployment, or restart. Neither the signed-shift trial nor
the following 15-row experiment is promoted. Speed, scrolling, physical rare
slowdown, and audio-fidelity acceptance remain open.

## Newly measured boundary

Fresh full-route instruction captures1959/1960/1961 compare parent and shift
trial alley entry and shift trial mall entry. Parent mall capture1924 is reused
with its source and trace hash checked. All complete timelines and PCM equal
their respective normal controls1918/1949. Audit1964 retains first three
main-to-fade iterations, original call-site preimages, matched-stack ordinary
NMI accounting, six frames of producer phases, and exact reset/wait boundaries.

| Alley event, offset from rendering enable | Parent | Shift trial |
| --- | --- | --- |
| First main-call entry | +1, line161 | +1, line161 |
| First fade call | +3, line233 | +3, line234 |
| End-of-loop wait first reached | +3, line239 | +4, line97 |
| Next loop counter reset | +3, line239 | +4, line97 |
| Third main-call entry | +5, line163 | +6, line70 |

The small first-call timing difference crosses a hardware interrupt before
the trial reaches its wait/reset. First main-to-fade durations are812,894 and
814,042 master clocks. The actor call includes459,384/460,572 clocks in
ordinary NMIs; raw inclusive actor time must not be called exclusive actor
CPU work. Hidden row phases remain roughly113–116k clocks per16-row pass.

Mall is different. Parent first actor call costs371,302 clocks including
213,230 in ordinary NMIs; trial261,976 including211,840. Thus residual costs
are158,072 versus50,136, not matched actor workloads. First fade service is
parent+3 line146 versus trial+2 line162; the following service is+4 line201
versus+3 line215. This does not prove a publication-only fault or that the
small arithmetic patch directly saved all that work. The fixed-offset
graphics failures remain retained; no gate is waived.

## Isolated 15-row experiment rejected

Existing `build_hidden_budget_trial.py` changes only the guarded state-2
budget immediate16→15 and checksum: three ROM bytes total. Candidate1962
SHA `855fc069260e09e5d8047cad2ed17f51e89d61a952489349888b4f280a064486`.
Its purpose was to test whether a slightly shorter producer pass creates
margin before the observed alley interrupt boundary, without changing game
timers or publication ownership.

Full normal capture1963 completes9,037 frames. The unchanged NES oracle in
[entry1965](http://127.0.0.1:8766/shift-hidden15-entry-1965/) **fails**:

- First scenery after enable:8/7/7, NES7/7/7.
- Room-change latency:21/27/28, NES20/31/30.
- Rendering-off latency:21/28/28, NES20/31/30.
- Alley fixed-offset fades differ; mall and park match all40 offsets.

This does not resolve the alley failure. Earlier boot/load phase changes also
change later encounters, so the whole-run budget comparison is not a clean
same-state causal test. No further fixed-budget sweep was performed.

## Checkpoint harness is now qualified for observation and immediate roundtrip

New `tools/capture_route_checkpoints.py` wraps the existing controller-driven
capture without changing historical scenario definitions or observer sources.
It uses the core's local `retro_serialize` / `retro_unserialize` implementation.
Inherited RCR instrumentation is forbidden because historical instruction/span
trace clocks do not support state restoration. State binaries are diagnostic
artifacts, not served ROM downloads or normal input-only acceptance captures.

On the exact shift candidate1947 and same DSP-capable core with observers off:

- `shift-checkpoint-save-1966`: save-only at frames2426 and5956.
- `shift-checkpoint-roundtrip-1967`: save and immediately restore at those
  frames, then continue the same input policy.
- Both complete all8,936 frames. Full video/RAM/native telemetry/input
  timelines and complete PCM match uninterrupted1949 exactly.
- Both states are823,407 bytes. Their hashes and originating frame/RAM hashes
  are bound in each `checkpoint-report.json`.
- This **does not yet validate fresh-process restoration or cross-ROM
  counterfactuals**. Those fields explicitly remain false in the reports.
  No speed/audio improvement is inferred from checkpoint neutrality.

Tests now total **1,001 passing** (`/tmp/rcr-tests-1968.log`). Added tests
reject duplicate/out-of-range checkpoint selection, wrong-bank markers and
missing completion boundaries. The full same-core equivalence validator also
rejects changed PCM, state, input, ROM, core and incomplete captures.

Next: validate a fresh-process same-ROM resume against the exact recorded
suffix, including callback PCM boundaries, before a cross-ROM budget trial
from the same checkpoint. Keep uninterrupted whole-route tests as separate
release gates; checkpoint diagnostics must not replace them.
