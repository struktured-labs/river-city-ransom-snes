# Compact paired rows: same-state school update misses one fewer frame

[Before/after collages, native audio and source bindings](http://127.0.0.1:8766/compact-pair-review-2265/)
· [Remaining independent combat failure](http://127.0.0.1:8766/compact-pair-combat-review-2249/)

Offline candidate2242 SHA256:
`f7f8e725acaaef5592ededba9149ce17e1d7a43767a8deae739f825270c6c829`.
Parent is [camera-deadline candidate2221](CAMERA-GUARD-REPROBE.md).
No Rival restart, controller input, OBS change or deployment. Full-game
original-speed parity, long camera holds and physical audio pops remain open.

## Why this experiment

Fresh running/jumping instruction captures2240/2241 match all4,912 timeline
frames and PCM from same-core control2239. The first post-school-return main
iteration starts at4013 and finishes at4016. Hidden row preparation still costs
roughly108–114k elapsed master clocks per heavy pass. Its actor-update call
contains680,410 clocks, including454,196 in complete ordinary NMI spans.
The later FAD6 call crosses another interrupt; original fade service occurs
at4016 line85. Costs include DMA/events and cannot be added to their children.
Raw instruction windows are retained; full-load RTI matching can be ambiguous
when interrupted code repurposes the stack, so no multi-frame NMI cost claim
is made from a naive same-stack match in that part of the trace.

The old guarded two-row DMA implementation was previously tested without the
new compact index. Combining them removes repeated DMA setup for eligible
adjacent rows. This is not a row-budget or fade-counter change.

## Surgical implementation

`tools/build_compact_pair_reprobe.py` first reassembles the exact779-byte scalar
compact helper and compares every byte with the current cartridge. Its entry
atC0:A77D receives JMP D500. The928-byte combined helper is installed in a
previously FF-filled1,280-byte regionC0:D500–D9FF; only that region, the three
entry bytes and checksum change. The active15/16 row-budget helper immediately
after the original body is untouched, as are palette, camera-deadline, OAM,
arithmetic, audio and render-edge scheduling changes.

The paired implementation retains even-row/neighbor eligibility, remaining
row and scan budgets, exact dirty/unqueued ownership, mixed-alias fallback,
high-byte duplication and forced blank. Original tile data is unchanged.
`pair.lbl` describes the active relocated helper; old internal symbols remain
historical and must not be used as active helper profiling points.

## Actual production-byte oracle

Oracle2247 executes1,024 cases. Before each ordinary scalar fixture is run,
its entry receives the exact production trampoline and its free D500 region
receives the exact candidate bytes. No relocation/reconstruction of the code
under test is substituted. Sixteen selected starting rows cover ring, page,
quadrant and parity boundaries, crossed with both mirror/pattern halves,
budgets1/2/15/16, one/two calls with changed data, and mixed/all-dirty aliases.

The independent oracle checks all8,192 actual tilemap VRAM bytes, source,
immutable staging, all row flags/requirements, cursor and remaining budgets.
Four executed binary mutants fail: wrong pairing parity, short paired length,
short high-byte duplication and missing extra-row budget accounting. Fixture
ROM/RAM/receipts/logs and production bindings are hashed. This is not all128
starting rows, injected-interrupt testing or full-game state equivalence.

## Identical-state replay: real school-return improvement

Checkpoint capture2251 is neutral to control2239 over all4,912 frames and PCM.
Fresh-process controls2252/2253 each reproduce180 frames exactly. Trials2254/
2255 require the exact newly assembled patch, identical full128KiB initial
WRAM, all saved CPU registers and the same recorded physical inputs. Neither
checkpoint is inside the helper. The existing replay engine is reused without
changing its historical source; the new wrapper admits only this patch.

| Same school-return state | Parent2221 | Paired2242 |
| --- | ---: | ---: |
| Rendering enable | 4012 | 4012 |
| Load completion interval | 23 frames | 23 frames |
| First post-return completion interval | 3 frames | 2 frames |
| First scenery after enable | +8 | +7 |

Counters are observed at frame boundaries, not advertised as exact-PC endpoints.
The authenticated initial RAM sample is prepended to avoid losing an edge at
the first replay frame. All interior completion changes and censored boundaries
remain explicit. The alley replay preserves enable2569 and regular subsequent
two-frame completion spacing; its initial15-frame loading interval starts at
the checkpoint boundary and is not fully measured there. The independent
combat test below retains that failure.

## Independent qualification, including failures

- School2245/2248: all40 fixed NES fade offsets match, first scenery+7;
  room/off-to-visible27/28 versus NES34/34.
- Forward2246/2250: full9,225-frame route completes; all40 fixed offsets in
  rooms1/2/3 match, first scenery+7 throughout, whole-load limits pass.
- Combat2243/2249: both normal/observed pairs match fully over4,913 frames.
  Sustained attacks passes1,661 loops. Running/jumping has1,655 loops and
  still fails at the15-frame alley load2556–2571 (8 NMI advances). This new
  encounter does not return to school; its missing school outlier is **not**
  treated as proof of the same-state improvement above.
- Renderer2256/2261:7,618 complete eligible frames,6,657 covered held-camera
  frames, zero missing coverage/split/stale-camera failures.
- Cadence2259/2260/2262:3,741 stable two-tick loops pass across four rooms.
  No short irregular park holds. **Thirteen14-frame holds remain** (ten east,
  three west), versus seven in the independently encountered parent route.
  Changed encounter work prevents calling this a same-state hold regression
  or claiming those long holds fixed.
- Audio2257/2258/2263:8,783 packets,202,009 received bytes,1,623 restarts,
  zero late writes; late-write negative control rejected. Raw DAC equals
  4,918,005 native stereo samples at32,040Hz, peak6,724, no clipping.
  This does not certify NES waveform fidelity or pop-free physical audio.

Each observer has its own same-core full-timeline/PCM control. Six new unit
tests cover patch bounds/preimages/occupied space, unchanged neighboring
scheduling bytes, exact fixture injection, malformed/ambiguous mutations and
the saved initial-frame boundary. Full suite:1,081 tests pass
(`/tmp/rcr-tests-2266.log`).

## Next

Follow-up: [like-for-like counter comparison2356](LOAD-COUNTER-COMPARISON.md)
finds that the remaining15-frame alley load also takes15 frames on the NES.
Both original game counters reset at+13 and finish at2; historical SNES8 used
a different native NMI counter. Whole visibility latency and all40 fade
offsets match. The historical strict result above is retained, not rewritten.

Follow-up: [current park-hold audit2273](CURRENT-PARK-HOLD-ORIGIN.md) explains
all19 long intervals (not just the13 equal-two-pixel endpoint holds) as repeated
camera commands with regular complete main loops and next-frame publication.
Fresh NES observations support the same behavior category. This does not clear
the older unmatched physical recording or classify the underlying game action.

Keep the retained loading intervals and original waits in all acceptance
reports. Establish whether the long park holds are original game motion or
port-specific, with matched work/state evidence. Requalify menus/status and
the actual camera/fallback worst-case workload before promotion, then use the
native hardware audio chain to classify remaining audible pops. This candidate
is useful progress, not a release or permission to bypass the original-speed
benchmark.
