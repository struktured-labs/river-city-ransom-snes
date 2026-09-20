# Camera deadline: sustained-combat missed interrupt corrected offline

[Review, collages and native audio](http://127.0.0.1:8766/camera-guard-review-2238/)
· [Remaining combat failures](http://127.0.0.1:8766/camera-guard-combat-review-2232/)

Candidate2221 SHA256:
`f6d7f6c454863d181a9e72eff49f5427bc6569b278f71fc07f8db609b359241d`.
Parent2197 is the [palette comparator trial](PALETTE-COMPARE-SPEED.md).
Offline only: no Rival restart, OBS change or physical input. Full-game speed
and physical popping remain unresolved. The last deliberate Rival load remains
the [slower fixed-note splash2089](SLOW-WUB-TAIL.md).

## Change and boundary proof

The parent loses an ordinary interrupt when camera-tail graphics preparation
starts at frame2081 line238 with NMI masked and finishes next frame line17.
The historical line194 deadline is now relinked on the faster current parent,
not promoted as a newly proven worst-case bound. Late work keeps its existing
pending ownership and is serviced by the unchanged interrupt-exit fallback.

Builder `tools/build_camera_guard_reprobe.py` patches one camera JSR operand
in each of C1–C8, installs the same128-byte guard at7F00–7F7F, and updates
checksum. Existing OAM, early-preparation and arithmetic helpers remain intact.
No graphics, game timers, SPC code or regular default build changed.

Oracle2229 executes36 real-beam cases spanning lines192–260 and three entry
delays, rotating all eight program banks. Actual candidate guard/service/
fallback bytes are included, but the graphics bridge is a cycle-burning spy.
Active-display cases retain exactly one NMI and service; high-bit cases leave
pending work intact. X/Y/DP/DB/SP checks pass. Unguarded line231 reproduces
the missed interrupt. Three binary mutants fail: late cutoff, dropped beam
high bit, wrong early cutoff. This is not a production worst-case execution
bound or full graphics-state oracle.

## Full production scheduling observation

Same-core normal2230/observer2231 match all4,912 frames and native PCM.
The16-point host-only trace observes guard decisions, actual service/fallback
entries/returns, four graphics phases, ordinary NMI and main-loop boundaries.
Audit2235 checks ordered ownership without modifying the cartridge:

- 1,752 admitted services all finish in the same frame before line240.
- Two deferred jobs are serviced exactly once; two empty guard calls remain.
- All3,510 eligible stable NMI-enabled frames have exactly one NMI entry.
- Every serviced job contains the actual producer/palette/sprites/tail phases.
- All ordinary producers on fallback ticks remain in the report; none are
  hidden to make the cost appear smaller.

Maximum observed admitted service is68,664 elapsed master clocks. That maximum
is empirical, not a universal bound supporting every future workload.

## Independent regression results

- Combat2222/2232: sustained attacks now passes1,661 measured loops. Running/
  jumping still fails, with1,644 loops and15-,23-,3-frame outliers. Complete
  4,912-frame same-core normal/observed pairs agree. Every outlier has contextual
  screenshots and exact native PCM; no transition failure is waived.
- Full traversal2223 completes8,874 frames. Forward audit2227 matches all40
  fixed NES fade offsets in each of three rooms, first scenery+7, and passes
  room/off-to-visible limits. School2224/2226 matches all40 offsets, scenery+7,
  whole loading28 versus NES34. Independent encounters are not equal-work proof.
- Renderer2225/2228 matches same-core normal2223:7,266 eligible frames have
  complete coverage, zero camera splits and zero stale-camera failures.
  Park uniform-endpoint holds are east {2:217,14:4}, west {2:144,14:3}.
  No short1/3/4-frame irregular holds; all seven14-frame holds remain explicit.
- DSP2233 matches normal2234 across8,874 frames. Audit2236 passes1,548 note
  restarts with zero late writes and rejects an injected late-write observation.
  Raw DAC/PCM transport checks are not a subjective or physical pop-free verdict.

Eight new unit tests cover all-bank patch scope, missing/ambiguous call sites,
occupied helper bytes, malformed images, complete/empty/deferred ownership,
late services, truncated paths, duplicates, reordered phases and interruptions.
Full suite:1,075 tests pass (`/tmp/rcr-tests-2237.log`).

Remaining work: qualify the real worst-case camera/fallback workload, resolve
running/jumping transition timing without regressing fades, retain native
physical audio evidence and clear actual popping. Do not deploy this speed
trial on the strength of one passing combat policy.

Follow-up: [compact paired rows2242](COMPACT-PAIR-REPROBE.md) correct the
school-return3-frame update in an identical-state replay while preserving
fixed NES fades. The15-frame alley load and long park holds remain; offline.
