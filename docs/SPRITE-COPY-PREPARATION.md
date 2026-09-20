# Sprite-copy preparation: measured improvement, shorter loop

[Current collage, menu references and native audio](http://127.0.0.1:8766/sprite-copy-qualified-3279/).
[Focused fresh cycle](http://127.0.0.1:8766/sprite-focused-fresh-3267/).
[Actual old build rejected](http://127.0.0.1:8766/sprite-focused-negative-3268/).

Candidate: `build/sprite-copy-game-3252/native-cpu.sfc`.
SHA256: `0ca9f0f4b7e9835d76d5089c7a2923e67518f83c19ba377496e632c97ab14290`.
Not deployed or release-ready. Rivalmage, Bluemage and OBS were not touched.

## Change

The existing NES OAM copy marked its shadow dirty but left sprite conversion
behind the larger producer's scheduling guards. Transfers could be safe and
byte-correct while displaying old generations.

`snes/sprite_copy_prepare.asm` calls the existing incremental sprite converter
immediately after the translated OAM copy, while interrupts are already masked.
The helper replays the displaced dirty latch, preserves A/X/Y/D/DB/P, and skips
the new work during initialization or hidden transitions. It does not move
background, CHR, palette or audio work. The existing converter requests OAM DMA
and clears the sprite-dirty flag, avoiding another full conversion later.

The builder checks all eight replicated hook preimages and the exact free helper
extent at C0:7800, rejecting occupied space or unrelated mutations. SPC bytes are
identical to3219 (`f22ccdd429c64fc8eb0f7e830ab8183fb938f0cbc85fe75babf11b0d371e009a`).

## Focused result

A 2,099-frame normal-input boot prefix observes frames1,978–2,020. Each arm has
its own exact same-core observer/control check; no emulated memory or restored
state is used. Source generation bytes and production frames match across ROMs.

| Known source generations | Parent3219 | Sprite3252 |
| --- | ---: | ---: |
| First rendered next frame |11|20|
| First rendered three frames later |4|0|
| Not rendered in the window |5|0|

Initial generation is left-censored, not silently assigned a latency. The source
generation denominator remains20, including updates the parent never displays.
Original game counter, logical camera and controller delivery match throughout
the prefix. Both arms show298 measured two-frame counter intervals after
frame1,500; no adapter faults. This is not full-game/NES latency equivalence.

The fresh one-command cycle took15.54s: normal capture6.38s, observed8.38s,
cached parent verification0.50s, plus reporting. Reusing the already-captured
trial is explicitly labeled and does not masquerade as a fresh-run timing.
The actual old build exits with failure solely on the next-frame-display gate.
Six targeted tests cover patch guards, missing/delayed generations, changed
sources, game slowdown, camera/input changes and false empty-population passes.

See [the workflow](FOCUSED-TEST-CYCLE.md). The installed reusable skill is
`/home/struktured/.codex/skills/romhack-test-loop/SKILL.md`, created with the
skill-creator workflow and validated with its validator. No global settings or
hardware permissions were changed.

## Broader checks after the improvement

- Complete9,248-frame route, same-core observer neutrality for each trace.
- All3,750 sampled original main-loop intervals across four rooms take two
  frames, including busy intervals in the established cadence oracle.
- Renderer:7,639 eligible frames, zero missing coverage, splits or stale camera.
- General DMA:56,205 transfers;54,351 VBlank,1,850 forced-blank,4 other;
  zero unsafe/aborted envelopes. Latest visible end line256. HDMA excluded.
- Audio: all8,802 complete CPU packet records equal the older3065 comparison;
  all1,607 staged restarts pass, zero wrong first pitch/stale nonzero onset.
- Present Status, pause cursor reopening, repeated purchases and YES/NO selection
  pass their NES pixel/state oracles. Known-broken cursor/shop controls still fail.
- Full unit suite at this checkpoint:1,313 tests in14.27s, OK. Diff check passes.

Review3279 validates3,355 source bindings and11 artifacts; focused3267 validates
609 bindings and16 artifacts. Both HTML pages were rendered and inspected.

Audio comparison is against3065, not the immediate3219 parent:992 image changes,
8,905 nonaudio timeline differences and852 audio callback differences are retained
in3266. The legacy3266 HTML has inherited wording about unchanged game code;
that wording does **not** apply to3252. Use the accurate3279 presentation and
complete3266 JSON, not that legacy prose.

## Still open

Subsequent exact3252 two-player stress is **not passing**: audit3292 retains a
three-frame original-loop interval in running-jumps, frames2239→2242 (three NMI
advances). That policy has1,751 two-frame intervals plus this one three-frame
interval. Sustained-attacks has1,753 two-frame intervals and passes. Both normal/
observed pairs have4,929 frames and exact same-core neutrality. The prior3219
passed both policies. The new sprite placement therefore needs a CPU-deadline
correction before promotion; the focused prefix improvement does not waive this
broader failure. Next speed iteration should pin this exact encounter/window,
not rerun the entire investigation. Evidence:
`build/sprite-copy-combat-review-3292/report.json`.

All1326 tests, including the agents' new AI/shop and tracker tests, subsequently
pass in14.54seconds. This further illustrates why unit PASS is not runtime speed.

Sprite freshness beyond the selected window, broader
original-NES fidelity and physical pop-free audio/video acceptance. Clean DSP
restart timing does not prove that all audible popping is gone. AI-assisted P2,
including controller-one access to P2 equipment, is an independent prototype and
not part of these results. The complete speed/scrolling/audio objective remains
active; neither a narrow PASS nor a skill installation completes it.
