# Paired CHR decompression read — rejected

The current dead-mailbox candidate's fresh 12,000-frame profile (warmup
1,800) is `build/dead-mailbox-profile-01.json`. Its completed NMI intervals
are 10,103 one-frame intervals, three four-frame intervals, four eleven-frame
intervals and one twenty-two-frame interval. No two-frame interval or
VBlank-overrun flag appears in this particular measured run. Boundary stalls
remain separately represented; this is not universal gameplay-speed proof.
Long stalls sample adapter/load code, motivating a decompressor experiment.

The experiment resolved adjacent CHR bytes once instead of resolving each
of the dummy/buffered reads independently. It was guarded to CHR addresses,
increment one and no 256-byte page crossing; all other cases used the old
two-read path. Existing adapter tests passed, including a CHR sentinel,
final read-buffer value, address increments and register preservation.

However `build/chr-read-pair-quality-02/snes` took 2,040 baseline frames,
one more than the 2,039-frame parent. Reorganizing the CPU-memory source path
to avoid an added long jump did not help: `chr-read-pair-quality-03/snes`
also took 2,040. The guard/branch overhead is not justified by these results.
The source changes were reverted. Experimental captures remain available;
they are not release candidates and were never deployed.
