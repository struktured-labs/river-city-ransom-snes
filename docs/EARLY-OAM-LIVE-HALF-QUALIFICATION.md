# 3955: broader graphics qualification

Exact ROM `f6f69215716ecc077c9082da0a20db1eaaa064daab81b0992a54cade834d1e16`.
No promotion, deployment or physical-console acceptance. This follows
[the implementation and focused tests](EARLY-OAM-LIVE-HALF-CURRENT.md).

## Fresh scoped results

- DMA3969/3970/3971:53,643 general transfers pass;51,710 VBlank,1,929 forced
  blank, four other. Latest visible end259. Active-scanout, crossed-frame and
  unfinished-transfer mutations fail. HDMA is outside this observer.
- Renderer3972/3973/3974:7,473 eligible/6,502 held frames pass with no coverage,
  split or stale-camera failure. Same-core complete timeline/native PCM neutral.
- Present Status3978/3979: fresh2,537-frame replay; opening/reopening numeric
  regions match NES3652 with zero mismatched pixels. Not all menus/shops.
- Palette3980–3983: strict prefix gate now passes. All four shadow/prepared
  stages match3695 at every frame; eleven CGRAM colors arrive earlier, none
  later or unsupported. The former2429 source-phase difference is absent.
  Known-bad3780 still fails with eleven late colors. This is2,579-frame coverage,
  not original-NES palette timing everywhere. Fresh prefix6.292s,12.781s with
  full-prefix verification; CGRAM control/observed replays6.272/6.206s.

## Full-route physical sprite memory and blanking coverage

Neutral3976 observes8,638 production uploads:155 full544 and8,483 partial256.
All544 actual OAM bytes match staging after every upload. Every recorded
sprite-render span also has the correct288-byte static tail. The strict R-only
audit3977 nevertheless fails coverage:57 partial-render frames and131 frames
without R events. Those results are retained, not waived as inferred blanking.

New read-only core3984 records B at the exact existing branch that fills pixels
black. Fresh normal3985 matches old-core3975; observed3986 separately preserves
its same-core full9,090-frame timeline and native PCM. Replay22.567/26.447s;
total27.839/32.033s including verification. The old3975 control was finalized
without replay after correcting an inappropriate same-core check on its
explicitly cross-core comparison; verification5.076s, no fresh replay claimed.

Strict exact-once audit3987 identifies one remaining anomaly: the core fills
line19 of frame307 black three times. Corrected classifier3989 accepts only
identical B→B writes; R→R, R→B and B→R overlap, missing spans and wrong blank
flags still fail. Both redundant black writes remain explicit. All9,090 frames
are fully accounted for by8,969 render and1,150 black-span events, with zero
physical-OAM or classified coverage errors. Corrupted untransferred-tail and
missing-black-span controls fail. Thirteen new unit tests cover memory gates,
hook insertion and strict/idempotent coverage. Earlier failed audits are intact.

## Remaining scope

Broader shop/menu scenes, mirror-row latency, ALEX source phase relative3890,
matched original-NES gameplay speed, acoustic acceptance and physical SNES
Junior/EverDrive validation remain open. Existing two-player tests pass but are
not matched NES encounters. This turn changes only test tooling/documentation,
not the cartridge. Audio's worst packet gap is unchanged; the next measured
target is [the command-acknowledgement stall](CURRENT-COMMAND-ACK-STALL.md).

- [Full OAM and actual blank spans](http://127.0.0.1:8766/early-oam-live-half-blank-review-3989/)
- [DMA](http://127.0.0.1:8766/early-oam-live-half-dma-review-3971/)
- [Renderer](http://127.0.0.1:8766/early-oam-live-half-renderer-review-3974/)
- [Present Status](http://127.0.0.1:8766/early-oam-live-half-status-review-3979/)
- [Palette and failed control](http://127.0.0.1:8766/early-oam-live-half-palette-review-3983/)

OAM and palette pages rendered and visually inspected. All links are local;
no ROMs or RAM/state payloads are published by these review pages.
