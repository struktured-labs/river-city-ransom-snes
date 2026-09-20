# Visible attribute cache: correct, not promoted

Candidate665 (`1a955af48ae0077188a0c13d439ed863d6329b6707779dc0783c8eb34e22c895`)
adds an invocation-local cache to the fused visible-row producer. This is
default-off (`--experimental-visible-attribute-cache`) and requires fused rows.
No Rival restart, hardware input or OBS setting changed for this experiment.
The current-source disabled build669 is byte-identical to parent608.

## Implementation and executed oracle

Sixteen palette/pattern words occupy private low-WRAM `$1B60..$1B7F`;
the key is producer scratch `$1E26..$1E27`. Each producer entry invalidates it.
The physical attribute address and vertical quadrant select the key; pattern
half and shadow contents cannot change inside the NMI-masked invocation.
Tile conversion, mirror aliases and immutable queued-row ownership retain
their existing semantics. This changes no original game graphics or game RAM.

`visible-cache-low-oracle-664` executes384 cartridges covering all256 consumed
attribute values, both mirroring modes and pattern halves, sixteen boundary
starts, budgets1/2/10 and one/two calls with changed source and pattern half.
It checks all8192 staging bytes,128 flags, source shadow, actual VRAM,
initial requirements, cache boundary guards, DP/DB/stack and cursor/budget.
All six deliberately incorrect variants are detected: missing invalidation,
quadrant or page, unconditional reuse, wrong bank and wrong assembler width.
The earlier high-WRAM implementation661 is retained, but665 supersedes it.

## Actual timing and full-route outcome

Master clocks from real producer entry to palette preparation, with timing
observer WRAM equal to the corresponding normal execution:

| Start row / budget | Parent | Candidate665 | Clocks saved |
| --- | ---: | ---: | ---: |
|0 /1|11272|11462|-190|
|0 /2|23682|20428|3254|
|1 /2, quadrant boundary|23688|23924|-236|
|2 /2|23694|20416|3278|
|28 /2|23682|20428|3254|
|31 /2, nonvisible boundary|24600|21386|3214|
|0 /10|112834|96452|16382|

An adjacent two-row case is about14% faster. Cold-cache cases are slower.
This is not14% faster gameplay. Normal, renderer and background-observer runs
complete the8629-frame input-only route; observers match their own normal
timeline and PCM. Actual uniform2px camera1/3-frame hold pairs remain:

| Route | NES | Parent608 | Cache665 |
| --- | ---: | ---: | ---: |
|Park east|3|11|14|
|Park west|0|18|19|

The full histograms retain long stops and censored boundaries. Encounters
differ, so this is not equal-work combat speed. It does establish that this
optimization alone has not fixed the presentation-pacing defect.

Renderer tests show zero splits across7315 eligible frames and zero stale
holds across6385 eligible unchanged-camera frames. Their real broken-ROM
controls are detected. Background comparison has773 exact positions across
four rooms (259/103/110/301), but publication and settling gates still FAIL.
836 frame-end camera warnings are retained, not treated as a release score.
Short movement passes21px versus21px; this is only a32-sample movement probe.

The first status capture667 lacked full per-frame RAM telemetry and was
correctly rejected by the audit. Capture669 repeats the same input-only
scenario with telemetry enabled; the original evidence is retained.
First opening and reopening both pass with zero status-region pixel mismatches.
All544 Python tests pass; `git diff --check` is clean.

No new sound treatment, full-route acoustic qualification or controller-mode
change is claimed. Keep this cache experimental. Next target: the phase of
graphics producer work relative to the original two-NMI gameplay loop, while
preserving original game ticks, every-frame audio service and queue ownership.

Review: <http://127.0.0.1:8766/visible-cache-review-669/>.
