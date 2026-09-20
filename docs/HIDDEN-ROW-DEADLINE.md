# Beam-bounded hidden rows: scheduling evidence, no promoted candidate

Rival remains on `fa882cb61138`; no inputs, restart, OBS change or deployment.
Review: <http://127.0.0.1:8766/hidden-deadline-review-1414/>.
Exact call schedule: <http://127.0.0.1:8766/alley-fade-schedule-1408/>.

## Original NES comparison

New original NES capture1402 observes eight exact PCs during frames2100–2145.
Its entire 8,548-frame timeline and PCM equal NES baseline331. Compact12
instruction capture1403 likewise equals its complete 8,808-frame normal1392.
Schedule audit1408 also revalidates the current cartridge's complete neutral
instruction capture1374 against normal1322. Each observer is compared with
its own baseline, not asserted equivalent across different cartridges.

The first three main-start/fade-service frame offsets after the state-selected
alley rendering-enable edge are:

| Build | First start → fade | Second | Third |
| --- | --- | --- | --- |
| NES | +1 → +3 | +3 → +4 | +5 → +6 |
| Current16 | +1 → +4 | +4 → +5 | +6 → +7 |
| Compact12 | +1 → +3 | +3 → +5 | +5 → +7 |

Compact12 restores initial fade setup, but its next service is still late.
That second iteration includes 226,596 clocks of ordinary NMI inside the
sprite-list call and 178,880 inside the actor-update call. The complete
matched call records and frame-end fade flags, levels and ticks are retained.
NES CPU cycles and SNES master clocks are different units; these are not
equal-encounter speed ratios. FCEU's reported line240 persists during VBlank,
so it is not treated as a precise physical start scanline. A fade-service
call does not necessarily generate colors.

## Scheduling prototype

`snes/hidden_row_deadline.asm` is an opt-in 37-byte wrapper around the already
verified compact direct-row helper. After a complete row and its owned mirror
have finished, it reads the real vertical beam. At/after the chosen cutoff
and before line240, it sets the remaining row budget to1; the existing caller
then decrements it to0 and marks remaining work. Late VBlank is left alone,
and the existing maximum16-row budget always applies. No new-frame wait,
mid-DMA interruption, original fade-counter change or room-specific policy.

The patch builder requires the exact existing transition-state-2 guard and
unique direct-row call, verifies unused padding at `$C0:D300..FFC0`, and edits
only two call-operand bytes, that padding and the checksum. All original
converter/ownership code, game logic, graphics and SPC bytes remain unchanged.
Tests reject invalid deadline values, missing/duplicate guards and occupied
padding before writing an output directory.

These are full-route experimental executions, **not** complete new-wrapper
ABI/beam-boundary/ownership qualification. No prior cadence, renderer or
acoustic pass is inherited. All prototypes remain unqualified for release.

## Every tested cutoff and failure

| Policy | First scenery after enable, rooms1/2/3 | From room change | From rendering off |
| --- | --- | --- | --- |
| NES | 7 / 7 / 7 | 20 / 31 / 30 | 20 / 31 / 30 |
| Compact fixed16 | 8 / 7 / 7 | 22 / 28 / 29 | 22 / 29 / 29 |
| Cutoff96 | 10 / 10 / 10 | 23 / 31 / 32 | 24 / 32 / 32 |
| Cutoff112 | 8 / 7 / 8 | 21 / 28 / 30 | 22 / 29 / 30 |
| Cutoff128 | 7 / 6 / 7 | 20 / 27 / 28 | 21 / 28 / 29 |

Cutoff128 makes all forty alley and park fade offsets exact. Mall differs at
offsets6/10/14/18: the colors arrive a frame early. Its first-scenery and
room-change-to-visible gates pass, but rendering-off-to-visible still fails
in the alley (21 versus20), and the exact-fade gate fails in the mall.
Earlier colors are retained as differences, not quietly declared exact.

Cutoff96 remains hidden for nine sampled frames after enable and fails all
three initial visibility checks. Cutoff112 leaves alley and park offset7
wrong, with the mall exact. All three fail overall loading acceptance; no
phase alignment, deadline relaxation or cutoff selected separately per room.

Bound cartridges / normal runs / entry audits:

- Cutoff96:1404 /1406 (8,808 frames) /1409;
  `a4691d056be6d1e48e27cbdbf9476296a4bd19af68652fe326b65956baea2014`.
- Cutoff112:1411 /1412 (8,808 frames) /1413;
  `54722a9e718a75ed9a76614abf7bea3095caf1ac8ff9d4697c57573dfe175a8c`.
- Cutoff128:1405 /1407 (8,937 frames) /1410;
  `b7b977813fab78d9cfd89ea2b6ae1392509b8ba2b118a0320d75f077d0913152`.

Route duration is not an equal-work benchmark because encounter evolution
can differ. Original screenshots at a single fixed offset and all40-offset
reports are linked in the web review. 862 Python tests pass; the new NES
sequence checker rejects reordered/missing calls and wrong stack depth.

## Remaining work

Graphics readiness and original game work must both meet their deadlines;
limiting native work alone can simply keep forced blank active longer.
The first-visible/whole-load failures still block promotion. Full-game speed,
older physical camera holds and remaining physical audio gaps stay open.
