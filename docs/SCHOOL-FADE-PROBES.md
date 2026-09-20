# School fade scheduling: measured work and rejected implementation probes

[Every tested budget, screenshots, native audio and timing](http://127.0.0.1:8766/school-fade-probes-review-2182/)

No Rival/OBS changes or deployment. All candidates below remain default-off.
None meets the actual NES school-return fade oracle. This work does not resolve
physical pops or establish full-game original-speed parity.

## Fresh instruction evidence

Normal2144 and instruction capture2145 use the unchanged input-only school-return
policy and the same instruction-capable core on combined candidate2087. Both
complete2,877 frames; all video/RAM/input rows and native PCM match exactly.
The observed window is2650–2664, around rendering enable2653. Exact original
JSR preimages, stack-matched returns and complete ordinary NMI spans are checked.

| Event | First iteration | Second | Third |
| --- | ---: | ---: | ---: |
| First main call, offset after enable | +1 line151 | +3 line237 | +5 line217 |
| Original fade service | +3 line223 | +5 line204 | +7 line66 |

The first actor-update call (F299→8000) contains651,750 elapsed master clocks,
of which436,168 belong to observed ordinary NMIs. Hidden-row phases cost
roughly108–113k clocks per heavy pass. Palette, sprites, CHR and all original
calls are retained separately in the report. Costs include DMA/events; do not
add inclusive costs to their children or subtract them from acceptance timing.
No matched NES actor/instruction-work claim is made from these SNES traces.

## Controlled row-budget probes

`build_hidden_cap_probe.py` changes one byte in the exact existing budget
selector plus checksum: the idle cap changes, while active cap stays one less.
The source-assembled shift shortcut, branch layout, data, graphics, timers and
SPC are untouched. Controls2149/2150 reproduce180 frames each exactly from the
existing neutral combat checkpoints. The new replay guard permits only exact
active+shift composition plus this cap byte and requires identical complete
initial WRAM, saved CPU registers and requested/delivered inputs.

All tested values are shown; no favorable subset is selected:

| Idle / active cap | School enable→visible | Alley enable→visible |
| --- | ---: | ---: |
| 8 / 7 | 11 | 9 |
| 9 / 8 | 10 | 8 |
| 10 / 9 | 9 | 8 |
| 11 / 10 | 8 | 7 |
| 12 / 11 | 8 | 7 |
| 13 / 12 | 9 | 7 |
| 14 / 13 | 9 | 8 |
| 15 / 14 | 9 | 7 |
| Existing16 / 15 | 9 | 7 |

The original NES target is7. Smaller caps can starve hidden publication; merely
reducing the per-pass cap is not a solution. Every school replay retains the
23-frame completion interval and every alley replay the15-frame interval.
The16-row baseline comes from the earlier same-state combined replay; all
starting RAM/register/input comparisons are explicitly checked against it.
Candidates2146–2148/2157–2161, replays2151–2156/2162–2171, all remain diagnostic.

## Bounded work at the genuine rendering-enable edge

Two new assembly implementations replace only the transition1→2 STA with a
replicated helper atC1..C8:7F80, leaving the shift helper at7FC0 intact. Each
retains the STA, saves A/P, and performs one or two calls to the existing native
graphics bridge only when outside the original NMI, a running pipeline exists,
and PPUCTRL enables NMI. Startup and NMI-disabled paths retain their existing
synchronous preparation without an extra call. The adapter already masks NMI.
No original fade counter or fade/palette value is changed.

The producer remains bounded by its existing row budget. These prototypes move
work earlier while publication is hidden; they also extend the masked interval,
so they require audio/timing qualification rather than inheriting it.

- One pass2172: SHA `f95d2a4070ee8fb97f3e6aac4c234ce492e77e1e48353c3168269a7c9b07d394`.
  School capture2173/audit2174: room/off→visible29/29, enable→visible**8**.
- Two passes2177: SHA `0cee154f8df764f4af81a2d4a5a226b5bd182db68a6151ec23129b9378c7961a`.
  School capture2178/audit2180: room/off→visible28/29, enable→visible**8**.
- NES reference2140: room/off→visible34/34, enable→visible**7**.

Both improve on the combined parent's9-frame fade but still fail first-visible
and fixed40-offset fade equality. These are independent uninterrupted episodes,
not same-state causal comparisons. Full route2175 for one pass completes10,153
captured frames but **times out at park_00_west_sweep**. Its room-entry audit2176
correctly refuses incomplete coverage; there is no passing forward-entry result.
The two-pass full route has not been run. No failed outcome was waived.

## Executed ABI checks and limitations

Oracles2179/2181 each execute512 cases using the actual64-byte helper and hook:
guard values0/1/128/255 for depth, ready and PPUCTRL; eight D/I/V combinations
across program banksC1..C8 and DB81..88; E1/A8/X8/DP1B00. They check A, hidden B,
P, X, Y, SP, DP, DB, state2 store and exact bridge dispatch count. Mutants that
lose the state2 store or reverse the depth guard are rejected as executed
mismatches. The bridge is an intentionally clobbering RTL stand-in: these are
dispatch/outer-ABI tests, **not** real VRAM correctness or injected-interrupt
proofs. Actual game captures remain separate requirements.

The full Python suite passes1,055 tests (`/tmp/rcr-tests-2183.log`).
New tests cover cap range/preimages and exact all-bank patch scope,
occupied padding, duplicated/missing edges, repeat patching and bad helpers.

## Next target

Follow-up: [unused-sprite hiding optimization](OAM-HIDE-TAIL.md) authenticates
the one-pass instruction trace, proves palette generation is already late,
and removes measured OAM loop overhead. Forward traversal/entry now pass;
school return remains+8. The final main call still crosses the interrupt.

Profile the one-pass variant's first fade setup, subsequent original fade calls
and actual palette publication against its neutral control. Identify the
remaining frame before adding another scheduling policy: the second early pass
did not improve it. Keep whole-load latency and all fixed fade offsets, plus
forward traversal, menu, scrolling, combat and audio gates. Do not promote an
eight-frame return merely because whole loading is shorter than NES.
