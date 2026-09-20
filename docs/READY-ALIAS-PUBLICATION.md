# Ready-mirror publication, candidate 3890

Experimental, not promoted or deployed. ROM SHA256:
`67fa19ee60b76af7c8e7ec581075eabb97efb19e7ce933e2cc34db66882cbda2`.

## Change and measured symptom

Parent 3883 recovered the dialogue letter at frame 5989 but delayed the next
letter at frame 5991. Repeated scalar queue discovery/setup competed with the
visible and mirrored HUD/dialogue rows. Candidate 3890 adds a 151-byte helper
at C05000, called instead of the original scalar DMA trigger at C0842F.

After executing the original transfer, a 64-byte row may publish its ready
mirror immediately. Both rows use their own immutable staging bytes. The extra
transfer requires at least 128 bytes of original remaining budget and passes
the unchanged row_room beam gate independently. Dirty ownership, ages, original
row length, full accumulator, index registers and processor status are preserved.
No new persistent metadata, omitted mirrors or relaxed deadlines are introduced.
This deliberately changes queue scheduling: the ready mirror can precede other
queued rows. It is not an unchanged-order optimization.

Both targeted letters now match their own prepared tiles on frames 5989 and
5991. At frame 5990, the actual instruction trace shows visible row 25's DMA
trigger at line 247/cycle 840, a separate gate for mirror row 89 at 248/520,
and the mirror DMA trigger at 249/156. These are trigger timestamps, not a
claim of per-byte physical hardware timing.

## Exact-build qualification

- Ordinary route: 9,090 frames, unchanged game-counter/input/logical-camera
  trajectories versus 3883; all 70 changed pictures retained in gallery 3900.
- Text windows: 84 snapshots compared with 3843. Ten comparable words are
  current earlier, none later. The strict gate still fails: source changes on
  frames 5980, 5987 and 5988, plus one unsupported playfield word at 8236.
  Those observations are not waived or counted as equivalent.
  Follow-up source inspection: bytes 12043–12046 (ALEX) are zero in both builds
  at 5986, become C0 CB C4 D7 in 3890 at 5987, and reach the same value in the
  baseline at 5989. Bytes 1244B–1244F already have the later baseline value at
  the first captured frame 5980; onset is left-censored. These are source-phase
  differences, not proof of NES-correct scheduling or permission to align frames.
- General DMA: 52,046 envelopes passed (50,103 VBlank, 1,939 forced blank,
  four other); latest visible transfer end at line 258. HDMA is outside scope.
- Renderer: 7,473 eligible frames passed; 6,502 held frames checked. This does
  not prove every sprite, palette or text generation arrives on time.
- Two-player combat: sustained attacks and running jumps each run 4,930 frames.
  All 1,752 / 1,709 measured intervals, including busy contexts, are two frames;
  no off-cadence intervals or adapter faults. Exclusions and censoring are
  retained. This is not matched original-NES encounter-speed proof.
- Full native audio: 8,641 packets, 1,588 restart checks, 4,846,034 stereo sample
  frames; peak 6,432, largest adjacent step 4,530, no clipping. Stable packet
  spacing is 12.030–20.921 ms (3883: 12.351–20.933). The shorter minimum is a
  tradeoff, not a blanket improvement. All 1,298 excluded intervals remain
  available alongside the 7,342 classified stable intervals. Not pop-free.
- Palette prefix: 2,579 frames, compatible control core followed by exact-core
  neutral observation. The known bad candidate is still rejected for eleven
  late colors. Candidate 3890 has eleven earlier colors and twenty unsupported
  colors at frame 2429 because all four source/prepared stages changed.
  Its four stages and full CGRAM at 2429 equal the baseline at 2430. This
  establishes a one-frame phase difference, not original-NES timing correctness;
  the strict palette gate remains failed.
- Present Status: fresh 2,537-frame replay 3910; opening and reopening numeric
  display comparisons against NES reference 3652 both pass with zero mismatched
  pixels (review 3911). This does not qualify every shop or menu.

Observer runs preserve their same-core complete primary timeline and native
PCM. Cross-core compatibility checks are separate. Twelve emitted-helper,
prefix-search and audio-boundary unit tests passed in 1.771 seconds. The fresh
ordinary prefix replay took 6.011 seconds, 12.215 including full-route-prefix
verification. CGRAM control/observed replays took 6.037 / 6.095 seconds.

## Audit links

- [Every changed picture and native clips](http://127.0.0.1:8766/publish-ready-alias-gallery-3900/)
- [Text comparison, including unresolved differences](http://127.0.0.1:8766/publish-ready-alias-text-review-3896/report.json)
- [DMA](http://127.0.0.1:8766/publish-ready-alias-dma-review-3902/)
- [Renderer](http://127.0.0.1:8766/publish-ready-alias-renderer-review-3903/)
- [Combat](http://127.0.0.1:8766/publish-ready-alias-combat-review-3905/)
- [Full audio](http://127.0.0.1:8766/publish-ready-alias-audio-review-3897/)
- [Palette, including negative control](http://127.0.0.1:8766/publish-ready-alias-palette-review-3909/)
- [Present Status](http://127.0.0.1:8766/publish-ready-alias-status-review-3911/)

These links are workstation-local. Related open issues: graphics #18, speed #5,
audio #6. Remaining work includes source-generation attribution, unclassified
graphics, fresh menu coverage, original-speed equivalence and acoustic fidelity.
SNES Junior/EverDrive cold boot and physical sound remain unverified. No hardware
restart or deployment accompanied these results.
