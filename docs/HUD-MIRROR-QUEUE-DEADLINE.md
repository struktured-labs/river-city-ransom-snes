# HUD delay: mirror ordering meets conservative row admission

Fresh short-prefix instruction captures3748(parent3695) and3749(trial3743)
are independently neutral against their exact same-core controls. Both cover
all2579 primary frames/native PCM; instruction observations cover2472–2486.
Capture times7.255s and9.427s. Existing raw-state windows3741/3742 establish:

- At frame2472, visible HUD row2 and mirrored row66 are both staged-ready.
  Their64-byte staged payloads are identical. Original source appeared2471.
- Parent consumer starts89, encounters row2 first, then row66. Row2 is in VRAM
  for displayed2473. Trial consumer starts25, encounters row66 first, then row2;
  visible row2 reaches VRAM/display one frame later.
- The same ordering occurs for the health update staged at2484.

CPU observer frame2472: trial starts row scanning at line245/cycle396, admits
row66 through row_room at247/972, reaches row2's check253/276, then exits with
row2 still ready. Parent instead checks visible row2 at248/840 and row66 at
253/584. This is queue order plus admission time, not late HUD preparation.
CPU observer frames and rendered callback frame numbers are distinct.

The actual emitted row_room at C087E4 includes CMP #$F9 at C087FF: it admits
only before line249 in ordinary visible-mode VBlank. Do not confuse that with
the separate final-batch cutoff or later observed DMA completion lines.

## Tested tail-loop optimization3750

SHA256 `831d051423e3fcee7dc46def8340680a8ba3b54ada6bd7845197c46ddb6442ba`.
Only the C07380 queue helper and checksum change from3743. Remain byte-wide
through short scalar tails instead of reentering the group scanner after each
miss. Exact row order, scan budget and all DMA deadline checks remain unchanged.
The helper is135 bytes; the extension was verified unused before patching.

Four assembled-code oracle tests pass: all128 cursors ×128 empty budgets,
all128 ×128 single-ready placements,1500 randomized partial queues, verified
cartridge continuation opcodes and rejection of the historical bad jump target.

Normal3751 completes2579frames in8.020s. Finalized observed3752 is neutral;
replay7.825s, whole observer8.370s. Fresh instruction capture3753 is also neutral,
replay6.972s. At2472, the first-ready check remains essentially unchanged while
the second row-room check moves253/276→252/1278 (360 clocks saved relative to
the first ready event). At2484 it moves252/1196→252/826, likewise360 clocks
after removing the small entry-phase difference. Both still miss line249.

Disposition: optimization is structurally correct but DOES NOT fix the targeted
HUD regression.3750 is not promoted or deployed. It produces63 changed images
relative to3695, versus26 for3743; earlier boot/setup differences are retained,
not claimed improvements or accepted regressions. Original game-counter and
delivered-input trajectories remain identical in this prefix. No broad campaign
is launched for this unsuccessful symptom fix.

Next inspect the remaining final-batch DMA work. Determine whether row admission
still reserves a worst-case OAM/palette batch already performed by the early
publisher. If so, implement an evidence-based remaining-cost check with actual
DMA safety and publication tests; otherwise change visible/mirror scheduling.
Do not blindly raise the line249 cutoff or further optimize a360-clock detail
when the observed miss spans multiple scanlines. Full objective remains open.
