# Initial scene publication guard

Candidate: `build/transition-selective-03/native-cpu.sfc`, SHA-256
`59ad7f52c18b719de25c7b0c89e99eadf3d7a6f9324b890edee793e45d605f5f`.
Not deployed to Rivalmage.

## Mechanism

An original PPUMASK rendering-off write immediately disables SNES main-screen
layers. On the subsequent rendering-on write, snapshot which background rows
still need an initial publication. Preserve clean rows and current staged
rows, discard stale staged rows with newer shadow data, and rebuild rows if
the background pattern selection changed. Exclude nametable rows 30 and 31,
which the producer clears without a VRAM transfer.

The NMI consumer retires each initial requirement when it uploads that row.
Enable layers only after initial requirements and all CHR jobs drain. Later
animation writes do not indefinitely extend this initial barrier. Ordinary
scrolling does not arm it. The bounded readiness scan runs before the final
VBlank room check, not after it.

State allocation: `$1CA0` is 0 normal, 1 rendering off, 2 initial publication
pending. `$1E80..$1EFF` holds 128 initial row requirements. This is distinct
from live row flags at `$1D00..$1D7F`.

## Executed evidence

- `tools/check_adapter.py`: positive cartridge and negative controls pass,
  including case 19 for clean/dirty/queued/stale rows, excluded rows and
  pattern changes. Removing the explicit zero comparison makes a clean row
  falsely pending and fails case 19. Fast-write mutation is now anchored to
  its entry's DP setup because the expanded general dispatcher also uses a
  jump to the same data handler.
- `tools/check_video.py`: exact synthetic pixels and existing scrolling,
  clipping, cache and CHR controls pass. Omitting either final readiness
  bitmap word fails executed case 10. Initial publication counters retire
  once per upload.
- All 82 unit tests pass.
- Full retained-frame baseline completes in 2038 frames versus 2029 for the
  preceding candidate. All four original-speed transition gates still fail:
  boot/menu 211 vs 170, settings 69 vs 53, story 74 vs 54, street 484 vs 459.
- The 12000-frame pacing run completes, but includes a 23-display-frame NMI
  gap. This is not proof of original-speed gameplay or uninterrupted audio.

Local human-audit page:
`build/transition-selective-quality-03/street-audit/index.html`.
Explicit selection: 980, 981, 1000, 1025, 1026, 1027, 1030, 1054. Each PNG is
bound to both capture PNG and decoded RGB hashes. Frames 981 through 1025
are black; frame 1026 reveals the school background and Alex, with the
original progressive caption still in progress. The previous unguarded
capture exposed scrambled background strips at frame 1000. These are
separate runs, not a claim of matched game state at equal frame numbers.

## Remaining scope

This does not certify every transition or repair persistent mall NPC/shop
corruption. It does not prove sprite/palette publication is atomic in every
scene. Audio presence and transport checks do not establish fidelity or
absence of popping. Original-speed gates remain authoritative and failing;
the guard is a presentation correction, not a speed-completion claim.
