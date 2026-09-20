# Present Status missing stats

Issue [#4](https://github.com/struktured-labs/river-city-ransom-snes/issues/4)
was reproduced with ordinary inputs on native parent `67010b85…`. The labels
rendered correctly, but all forty nonblank numeric tiles were zero in the SNES
nametable shadow. Original NES CIRAM contained the expected digits.

## Cause and repair

Original bank 11's number printer directly writes `$2006` at `$BA6F` and `$BA75`,
then `$2007` at `$BA7B`. Those instructions were absent from the earlier execution
coverage and consequently had not been translated. Input-only NES replay
`build/reference-status-x11-168` proves the three sites execute.

`tools/build_native.py` now pins these exact code sites with three-byte preimage
checks. It does not scan arbitrary ROM data for register-looking bytes. The
known sites are appended to verified supplied coverage and deduplicated, so a
build using older traces still receives the repair. Existing hardware stubs are
reused; no game logic, graphic assets, audio engine, or interrupt timing code
changes. The standalone ROM differs by exactly **nine instruction bytes plus
four checksum bytes** from the prior parent.

The pinned build (`build/status-pinned-171/native-cpu.sfc`) and trace-derived
repair (`build/status-coverage-169/native-cpu.sfc`) are byte-identical:
`0555919b60acd05b25a98973292b29f508aefee3128f88a15ab9bc3a3c55613e`.

## Automated evidence

[Original / broken / repaired screenshots and complete gates](../build/status-release-audit-175/index.html)
include initial entry, repeated entry and a later encounter. All forty digit
tiles and the complete status-region pixels match original NES at the first
two entries. All sixty digit positions, including leading blank/hundreds slots,
also agree with the twenty current stat bytes in each game's RAM.

The original number-print callers read `$049F,X`, `$04A3,X`, … `$04C3,X`,
where X selects player 1/2. The independent oracle checks decimal conversion,
leading blanks, both players, SNES shadow and actual VRAM. The old executable
reproduces the missing digits as the negative control; unit mutations reject
a changed underlying stat and a stale final published digit.

After the independent encounters, NES stamina is 40 and SNES stamina is 63;
both displays match their own game RAM. This is not proof of identical combat
speed or enemy behavior, nor a claim that SNES stamina changed in that replay.

The complete **9,412-frame park timeline and WAV are byte-identical** before and
after this repair. This verifies no change on that unrelated route; its known
timing regression remains unresolved. The splash integration separately passes
all eight gates in [status-branding-audit-170](../build/status-branding-audit-170/index.html).

Reproduce the status audit:

```sh
python3 tools/check_present_status.py \
  --reference build/status-nes-167 --previous build/status-snes-166 \
  --candidate build/status-fixed-169 \
  --old-rom build/pause-cursor-coverage-117/native-cpu.sfc \
  --new-rom build/status-pinned-171/native-cpu.sfc \
  --park-before build/park-stress-snes-154 --park-after build/status-park-170 \
  --combat-reference build/status-combat-nes-172 \
  --combat-candidate build/status-combat-fixed-172 \
  --out build/status-audit-new
python3 -m unittest tests.test_status_mmio tests.test_present_status
```

## Rival deployment

At **22:02:39 EDT on September 16**, Rival was restarted using
`/media/fat/RCR-SNES-8bcff69.mgl`. Uploaded ROM SHA-256 was checked on the device:
`8bcff69c2a87c22cf71a809d99f17ef67d9dd7987d31767ca083d52cade0ce5d`.
It includes this stats fix and the already hardware-tested 48-frame bass fade,
not the experimental sprite-speed change. MiSTer process arguments confirm the
MGL, and [OBS's post-boot menu frame](../build/status-hardware-175/menu.png) confirms
handoff to the original game. This is boot/deployment proof, not yet a hardware
capture of the repaired stats screen; issue #4 remains open for that check.
