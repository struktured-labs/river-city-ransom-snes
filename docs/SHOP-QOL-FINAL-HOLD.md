# Final numeric shop results: opt-in confirmation hold

[Rendered offline audit](http://127.0.0.1:8766/shop-qol-final-hold-review-02/)

Candidate `build/shop-qol-final-hold-02/native-cpu.sfc`:
`8f91a4c139f0402968498ec001809e193ae31d1716b4872a71fdadbd01a283bc`.
Built strictly from pinned sprite-copy3252, not integrated into the current
speed/audio or AI-P2 candidates, and not deployed.

## Why there is a change

Actual numeric feedback already exists in the NES and port. Coffee says
`WILL POWER 2 Up.` repeatedly. Capped recovery reports the actual amount:
the second SNES cup says `STAMINA 9 Up.` for 54→63, not the nominal16.
Pancakes reports actual Stamina25/Max Power1, then Stamina1/Max Power7.
Different starting stamina from earlier encounters is retained in NES/SNES runs.

However, the **final** numeric result disappears automatically. Tea's completed
`WILL POWER 4 Up.` shadow occupies four four-frame checkpoints, roughly16 frames.
Visible publication lags that shadow: the earliest shadow-complete checkpoint
still has three pending dialogue tiles in VRAM, and the next has one. This is a
plausible explanation for missing the notification, not proof of the user's
specific experience or an exact every-frame visibility measurement.

## In-ROM implementation

The opt-in helper replaces the existing consume-finish call at C3:9200, using
verified free $7900..79FF padding replicated across translated banks. It keeps
the original result text until the consuming player's A/B buttons are released
and pressed again. It polls through the original game controller routine while
yielding through the original frame housekeeping, so a held advance cannot
instantly dismiss it. Statless items bypass the wait using the original item's
stat masks. No new RAM state, glyphs, stat grants, prices, equipment changes,
notifications or sound commands are added.

The initial unpolled experiment could not dismiss and remains preserved as a
negative control at `shop-qol-final-hold-01`. It is not a usable candidate.

## Verified and remaining

Fifteen ordinary-input purchases pass: thirteen Tea purchases naturally raise
Will15→63 and include a thirteenth capped purchase; two Pancakes purchases test
recovery and Max Power. Their actual stats and money match the untouched parent.
Each final message survives the hold and a fresh confirmation returns to the
item list. First advancement is deliberately held for120 frames, then released
for300 frames before confirmation. Runs took17.26s and9.01s including verification.

The original messages' fully published VRAM/pixels match the candidate's held
messages exactly. The first audit, which selected shadow-complete but unpublished
reference frames, failed and remains visible. The corrected audit selects by
shadow→VRAM publication, never pixel similarity; all rejected checkpoints remain
recorded. Historical `held_results` pixel fields describe that failed first
comparison; `publication_selections` describes the corrected publication-aware
comparisons.69 source bindings and5 gallery artifacts were revalidated; the web
page was rendered and inspected.

Six assembled-helper control-flow tests cover held buttons, fresh edges, correct
P2 ownership, statless bypass, occupied-code rejection and the failed unpolled
variant. These stub original-game callees, so they do **not** establish full P2
shop runtime behavior. Combined with the earlier model tests,11 focused tests pass.

Remaining: full P2/manual-management integration, statless-item real-shop replay,
broader shop types/consumables/equipment, current speed/audio candidate integration,
and hardware/audio acceptance. No consumed-item marker is implemented yet.
The original wording can also say `MAX POWER is maxed out.` for a zero overflow
gain below the real127 cap; this pre-existing misleading zero-gain wording is
retained, not silently counted as fixed by the hold.
