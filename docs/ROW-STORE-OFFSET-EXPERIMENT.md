# Row store-offset experiment rejected by full route

Candidate `build/row-store-offset-01` replaces eight INX instructions per
four-tile group with four fixed store offsets and TXA/CLC/ADC #8/TAX. This
removes three instructions per group without changing the row budget.

Isolated row oracle passes all visible tile words under both pattern halves,
menu/game budgets and mirroring. Wrong vertical quadrant and incorrect
store stride fail the executed oracle. Evidence `build/row-store-offset-oracle-02`.
The full adapter suite and all 125 Python tests pass.

Nevertheless **the game candidate fails**. Baseline total remains 1956 and
long route 7552, but the long route remains in room 1 at mall_right_00/03/07,
with camera 255, whereas the original is in rooms 2/3. Café CHR and menu
pixel gates fail (`build/row-store-shop-01/report.json`). The camera audit
refuses comparison because room identifiers differ. A completed input
script and unchanged total frame count are not sufficient validation.

Actual audio receive comparison passes 171120 bytes / 7440 packets, zero
mismatches, and cadence/raw-write audit completes. Observer timeline/WAV
are byte-identical to the normal candidate. This proves the observation is
non-mutating and packet bytes arrive; it does not prove audio fidelity or
make the gameplay regression acceptable. Reviewable PCM:
`build/row-store-audio-audit-01/index.html`.

The change is excluded from all game builds. Its isolated branch remains
under EXPERIMENTAL_ROW_STORES for further diagnosis and can be exercised by
`check_rows.py --store-offsets`. The exact reason for route divergence is
not established; do not label it merely timing noise or dismiss it based on
the standalone oracle.

Default rebuild `build/row-store-game-revert-01/native-cpu.sfc` restores
SHA256 `9d72565ce36e59b77343cd9454128b07fec46e38635cded4641b4e0b8f5fca44`.
No Rival deployment or claimed improvement.
