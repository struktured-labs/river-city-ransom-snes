# Guarded CHR pointer setup: less work, speed gate still open

Candidate `build/camera-safe-chr-low-539/native-cpu.sfc`, SHA256
`46ea51f64422d044be7eca90fc7d1aab01560cb1abee81dc41cca2b7bba7eaa0`.
Based on safe-camera521, with its anti-tearing guard retained. No Rival
deployment/reset. Default-off paired CHR reader remains default-off; this
change optimizes its already guarded path, not generic PPU reads.

## Implementation and executed tests

In `bulk_source_byte`, binary/increment-one/CHR/page-boundary guards already
exclude every case that needs generic nametable/palette pointer mapping.
Both cached and uncached CHR resolvers populate pointer high byte and bank.
Initialize only the low byte before that resolver, instead of calling the
generic shadow-pointer initializer and repeating address classification.
Lookahead, buffered-read mailbox, address increments, mapper invalidation,
caller preservation and interrupt policy are unchanged. Fallback stays intact.

Fresh matrices `chr-low-{scalar,paired}-oracle-540` execute256 cartridges:
pair off/on crossed with cache off/on, all32 CHR address pages, both inversion
modes, and all bank values within each fixture. They each reject six cache
mutants. `chr-low-pair-oracle-542` additionally rejects six reader mutants,
including the new missing-low-pointer store control. Boundary FD/FE/FF,
nametable and swapped-palette cases execute. This does not establish arbitrary
decimal-state or interrupt-edge equivalence beyond those fixtures.

All492 Python tests pass. No source/core mutation occurred during matrices.

## Current load measurements

`chr-low-load-541` is a complete9,408-frame CPU-observed replay; its full
timeline/PCM equals normal `chr-low-fixed-541`. Rendering-off boundaries are
2109..2123, versus parent's2110..2124. Earlier absolute startup is not faster
room-relative loading: the whole first load remains21 versus NES20.

Fresh profiles `chr-low-parent-cost-544` and `chr-low-cost-544` include the
generic pointer region, which earlier cost summaries omitted:

| Measurement | Parent521 | Candidate539 |
| --- | ---: | ---: |
| Generic pointer calls |920|536|
| Generic pointer own elapsed clocks |272,546|181,196|
| Reader + buffer + generic pointer + CHR resolver |1,021,874|932,828|

The selected nonoverlapping region total falls89,046 clocks (about8.7%).
Generic pointer totals include its other callers too. Instruction-entry
elapsed clocks contain refresh/events; not exclusive CPU cycles or a
whole-game speed ratio. Original waits remain counted, not shortened.

Entry audit542 still fails: loads21/28/29 versus NES20/31/30; visible fade
offsets7/6/7 versus7/7/7. Room2's earlier fade is not waived. No acceptance
gate was changed.

## Scrolling, menus and audio

- `chr-low-splits-545`: zero actual splits across7,235 eligible frames and
  1,157,600 renderer lines. Full8,550-frame observer timeline/PCM neutral;
  known broken renderer control detected.842 differences from frame-end
  committed camera remain recorded; these alone are not missed deadlines.
- Background audit545:784 exact samples, coverage259/103/110/312. Existing
  late-publication and settling gates still fail. Split freedom is not a
  latency or complete-scrolling pass.
- Status audit545: Present Status first entry and reopen both pixel-exact.
- SPC provenance545:9,233 packets, all received bytes/header/key-on/ready
  checks and full normal/observed PCM equality; processing161–1245 SPC ticks.
  No acoustic/pop-free or physical-capture certification.
- Park audit545: no stable packet interval above1.5frames. Neutral545:
  no late NMI interval in7600–8420. These are scoped, not endurance claims.

## Rejected adjacent-row experiment

Before the reader change, `camera-safe-pair-535` enabled existing adjacent
row DMA on parent521. Fresh oracle537 passes1,024 actual-VRAM/ownership cases
and six mutants, now including row budget16. It is a selected-start matrix,
not the old full-start matrix. Actual hidden stages shrink to106,156 /
106,190 /113,556 /29,380 clocks, but loading becomes22/29/29 and first fade
offset8. Full renderer541 remains split-free across7,385 eligible frames.
Helper improvement does not override worse loading: pairing stays disabled
in candidate539. No fresh audio qualification is claimed for pair535.

Next: retain the cheaper reader and coherent camera publication while
targeting remaining actual producer/main-thread deadlines. Original-speed,
scroll latency and audible/physical fidelity still require stronger results.

Review: `http://127.0.0.1:8766/chr-low-review-546/`.
