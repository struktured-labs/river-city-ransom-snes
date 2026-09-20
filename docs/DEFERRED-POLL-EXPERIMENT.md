# Rejected frame-poll scheduling experiment

`build/deferred-poll-01` moved gameplay sound processing/publication and
graphics preparation out of the original NMI return path. Gameplay NMI
instead marked one pending job; twelve checked original LDA $010B frame-poll
sites drained it before returning the original load result. Register/flag
preservation and the adapter's non-reentrancy guard were included in the
prototype, but it was not promoted to a fully validated scheduler.

The actual `deferred-poll-long-01/snes` route completed in 7553 frames, but
the experiment's unserviced-tick counter byte at $1CA3 was already 91 at the
moving-mall checkpoints, and 162 at mall_right_07. These are byte snapshots,
not an asserted nonwrapping total. A new NMI had repeatedly arrived before
the previous deferred job was serviced. Mall camera progress also diverged:
mall_right_00/01/02 were 0/76/162 versus reference 5/110/215.

Completing the replay is therefore not success. Polling placement failed
the once-per-frame service requirement and changed gameplay timing. No
audio-fidelity or graphics-equivalence pass is claimed for this candidate.

The runtime and polling hooks were reverted. Rebuilt
`build/deferred-poll-revert-01/native-cpu.sfc` matches retained
`literal-tail-buffer-01`, SHA256
`9d72565ce36e59b77343cd9454128b07fec46e38635cded4641b4e0b8f5fca44`.
No Rival deployment. Scheduling must use a reliable raster/frame event and
explicit service accounting rather than assuming the game polls every frame.
