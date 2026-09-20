# Palette comparison: school return fixed, combat pacing still blocks promotion

[Timing, three-way collages, native audio and source hashes](http://127.0.0.1:8766/palette-compare-review-2216/)
· [Forward fades](http://127.0.0.1:8766/palette-compare-entry-2204/)
· [Strict combat failures](http://127.0.0.1:8766/palette-compare-combat-review-2214/)

Offline candidate2197 SHA256:
`19bd6e462098fb863007c1a9438ace096fa3458107aa58dae3897f70aac10d53`.
Parent is the [unused-sprite hiding trial2186](OAM-HIDE-TAIL.md).
No Rival restart, controller input, OBS change or deployment. This is not a
claim that physical popping or full-game original-speed parity is solved.

## Implementation and real timing

The remaining school-return update previously finished just after an ordinary
interrupt. Native palette preparation compares16 shadow/cache words every
frame. The new helper unrolls that comparison using the same long-address
loads and CMP operations. On the first mismatch it restores the exact original
X index and comparison flags before entering the existing conversion code.
On equality it restores X=32, CPX flags and A8 before the existing sprite path.
No scratch RAM, new palette writes, original game timer changes or graphics.

The guarded builder replaces only the three-byte LDX entry at C0:AA9C with a
jump to previously FF-filled C0:D300–D4FF, plus checksum. The original startup
path, comparison fallback bytes, conversion and sprite preparation remain.
This is a separate default-off derived cartridge, not a default-build change.

Normal2202/instruction2203 agree across their entire2,872-frame school episode,
including video, original RAM, native state, inputs and PCM. The parent has its
own same-core neutral control2191/2192. Both use the same instruction core.
In the observed window, unchanged palette phases fall from2,628–2,668 to
1,806–1,820 elapsed master clocks. Changed-palette phases are slightly slower:
20,230→20,292 at the first sample, and20,256→20,332 in later samples. Every
observed phase is retained, including those slower paths. These are elapsed
clocks with emulator events, not exclusive CPU cycles or a whole-game ratio.

The first fade service moves from enable+3 line234 to line228. The first
iteration now reaches its finish/reset on+3 line235, before the interrupt,
instead of+4 line84. Four completed original fade palettes move from
+7/11/15/19 to **NES +6/10/14/18**. No fade counter was altered to force this.

## Executed comparator proof

Oracle2199 executes17,408 cases: all16 first-mismatch word positions and the
equal case, each with256 pattern/status seeds, in four DB/DP configurations
(0/0,0/1E00,80/1E00,7E/0). Single-bit differences cycle all16 word bits.
Entry is native A16/X16 in PB C0; status seeds therefore include duplicate
effective M/X states. Patterns and status are correlated, not fully crossed.

Actual helper and hook bytes are verified against the cartridge. A/hidden B,
P including width, X/Y/SP/DB/DP, the selected exit, and both unchanged32-byte
source/cache arrays match the original code. Three executed mutants fail:
wrong source word, lost comparison flags, wrong final X. No interrupt is
injected; this is not an interrupt-race or CGRAM correctness oracle by itself.

## Integrated regression results

- **School return2200 passes** all40 fixed NES background offsets, first
  scenery+7, room/off-to-visible28 versus NES34. No initial-startup substitute
  or selected-frame alignment. The published+7 image now shows the scenery.
- **Full route2201 completes8,874 frames. Forward entries2204 pass** all40
  offsets in each of rooms1/2/3, first scenery+7 throughout, and both whole-load
  latency limits. Independent encounters still prevent an equal-work ratio.
- **Renderer2211 passes**7,266 complete eligible frames and6,304 covered
  unchanged-camera frames: zero missing coverage, camera splits or stale holds.
  Both observer2209 and same-core normal2208 complete and match fully.
- **Cadence2212 passes**3,565 stable two-tick loops across four rooms and the
  short-irregular scrolling gate. Seven14-frame park holds remain explicit
  (four east, three west); they are not removed or declared fixed. Main2207
  and same-core normal2206 match fully.
- **Audio transport2210 passes**8,432 packets/193,936 received bytes and1,548
  restarts, with zero late configuration writes. Raw DSP DAC equals delivered
  PCM exactly:4,730,880 stereo samples at32,040Hz, peak6,571, no clipping.
  DSP2205 matches same-core normal2201. An injected late-write observation is
  rejected. This is transport/order evidence, **not** an audible pop-free test.
- **Combat2214 fails both policies.** Normal/observed pairs2213 each complete
  4,912 frames with identical video/RAM/input/PCM. Sustained attacks has1,661
  measured loops and a3-frame start interval at2081–2084 (two observed NMI
  advances). Original state is stable task C0, room unchanged, fade complete,
  unpaused, native transition0: it is not dismissed as loading. Running/jumps
  has1,644 loops and retains15-/23-frame room-change intervals plus a3-frame
  post-return interval. All four strict failures, contextual frames and exact
  native audio excerpts are published. No gate is waived.

Full Python suite:1,067 tests pass (`/tmp/rcr-tests-2215.log`). Seven new tests
cover exact patch scope, occupied space/preimages, all assembled word addresses,
first-mismatch flag restoration, equality exit, and complete/uninterrupted
matched-stack timing attribution. Review2216 validates288 current source
bindings and27 served artifacts plus its report. Combat review2214 separately
validates34 source bindings and34 served artifacts. The+7 collage was inspected.

## Next work

Follow-up: the [camera deadline reprobe2221](CAMERA-GUARD-REPROBE.md) removes
the stable sustained-combat gap in fresh tests, with full production ownership
and stable NMI-entry accounting. Running/jumping failures remain; still offline.

The [fresh combat instruction audit2219](http://127.0.0.1:8766/palette-compare-masked-window-2219/)
now identifies a recurrence of the missed-NMI bug. Control2217 and observer2218
match all4,912 frames and PCM, and equal the failing main-observer campaign.
In its first stable failure, the actual STZ4200 occurs at frame2081 line238;
one pending `second_tick_prepare_service` runs; STA4200 with bit7 enabled does
not occur until frame2082 line17. The masked window is56,222 elapsed clocks.
No ordinary NMI entry exists in frame2081; both surrounding frames have entries.
This is not a fade/load predicate artifact and is not waived as a two-tick pass.

The older [second-tick deadline experiment](SECOND-TICK-DEADLINE-EXPERIMENT.md)
already reproduced this mechanism, but its line194 cutoff regressed scrolling.
Do not blindly promote that historical guard. Bound late camera-side producer
work and its interrupt-exit fallback together, including duplicated passes and
generation/publication latency. Preserve the newly passing school/forward fade,
scrolling, cadence and audio checks while resolving this live regression.

The new source/cache comparator makes the requested timing more accurate,
but this candidate still lacks full speed, menu/status and physical audio
qualification. Native sound excerpts are available for audition; no subjective
listening result is inferred from packet counts or PCM equality.
