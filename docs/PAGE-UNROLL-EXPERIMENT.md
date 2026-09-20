# Rejected page-clear unrolling

Candidate `build/page-unroll-01/native-cpu.sfc`, SHA256
`5312ddc0ecd4a651a1491b1aec650f0f877c85ef03b86ecd850abf220c6b89c4`,
unrolled the 256-byte page store loop sixteen times per branch.

The full executed adapter suite passed. The page-fill mutation was adjusted
to omit the eighth store of each group while retaining its index increment;
executed case 16 rejected it. This verifies interior bytes, not only page
endpoints. The synthetic fixture ran faster, but the actual baseline game
retained exactly the parent transition durations: 168/58/61/480 frames
versus original NES 170/53/54/459. Settings and story gates still failed.
Evidence: `build/page-unroll-quality-01/site/index.html`.

The runtime change and its mutation-locator adjustment were reverted.
No hardware deployment. The retained candidate is `repeat-shared-01`;
this experiment does not improve measured game speed or resolve audio.
