# Packet-transfer latency separated from delivery cadence

The legacy SPC receiver in the pinned source waits for one token, copies
one byte from port 1, then echoes the token. Timers are checked in its idle
loop, not inside this transfer loop. Current CPU sender correctly publishes
data before the token and waits for all 23 echoes. This observation alone
does not establish that the protocol causes audible popping.

`analyze_spc_ack.py` now measures handshake ACK through final-byte ACK,
separately from inter-packet gaps. It uses master-clock arithmetic only for
ordinary active lines 0..223 in the same raw frame; wrap/overscan/short-line
windows are explicitly excluded. Initial ready waiting and DSP synthesis
are not part of this metric.

On the retained publisher-scan long trace:

- 7358 fully acknowledged packets.
- 6691 measured, 667 excluded from this timing calculation.
- Measured minimum 15278, maximum 15806, mean 15478.67 master clocks,
  about 11.35 ordinary scanlines on average.

Report: `build/publisher-scan-transfer-latency-01.json`, bound to the ACK
trace hash. Existing sequence, timeout and complete-packet checks still run.
New tests cover exact same-frame arithmetic, exclusions and backwards time.
All 132 Python tests pass.

This quantifies a transport cost against which a future protocol experiment
can be evaluated. A faster transport would still need actual SPC receive
byte equality, timer/DSP behavior checks and full game-route/audio testing;
lower transfer latency alone is not an audio-quality pass.
No game binary or Rival deployment changed.
