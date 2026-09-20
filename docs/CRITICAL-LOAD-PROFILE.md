# Restrict loading analysis to the rendering-off work

Current ROM is `audio-data-first-02`. The prior broad settings profile
included fade/palette work that was not the main rendering-off delay;
palette batching consequently saved no benchmark frames.

`data-first-movement-01/snes` and `movement-probe-02/nes` share the same
input prefix. Their frame-boundary original RAM shows:

| Phase | Initial task-zero wait, both | Final task-$80 run NES | Final task-$80 run port |
| --- | ---: | ---: | ---: |
| Settings | 21 | 2 | 3 |
| Story | 21 | 2 | 6 |

The port then spends 16 frames with initial graphics publication pending
and 13 with publication complete. The corresponding original task-zero
tail is 28 frames. These spans overlap the game's fade rather than being
independent additional waits; do not add all publisher frames to game delay
or remove the original wait. Frame-boundary observations are not exact CPU
entry/exit timestamps.

Fresh host-only instruction profile `build/load-critical-profile-01.csv`
covers raw frames 250..430. The captured full baseline timeline and WAV
are byte-identical to `audio-data-first-quality-01/snes`. Selecting windows
262..264 (settings) and 391..396 (story), corresponding to the observed final
rendering-off task runs, gives:

| Entry / instruction group | Settings | Story |
| --- | ---: | ---: |
| bulk_source_byte entries | 99 | 285 |
| ppu_read_buffer entries | 198 | 570 |
| chr_read_pointer entries | 198 | 570 |
| bulk_ppu_byte entries | 52 | 227 |
| chr_read_pointer instructions | 5544 | 15960 |
| bulk_source_byte instructions | 4455 | 12825 |
| bulk_rect_bytes instructions | 13691 | 11843 |

Original C872/C875 literal-loop sites execute 52/227 times respectively.
In story, source-byte reading and CHR address resolution are now substantial
remaining work. This is instruction frequency, not cycle attribution, and
the frame-window boundaries may include surrounding instructions.

Next investigate batching the literal command and its source resolution as
a unit. Merely replacing the two buffered reads has previously failed the
overall benchmark (`CHR-PAIR-EXPERIMENT.md`), so do not assume another
per-byte shortcut will improve the critical path. Preserve final read-buffer,
source index, destination/mirroring and interrupt semantics in any trial.
No ROM change or Rival deployment during this profiling run.
