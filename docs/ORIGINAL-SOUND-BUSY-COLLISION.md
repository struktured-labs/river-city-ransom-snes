# The first4007 sound difference is an original busy-guard collision

No cartridge change, promotion or hardware action in this investigation.
Do not remove the original guard or silently treat a no-op call as a normal
sound update. Retrying a skipped tick would itself change behavior and has
not been implemented.

## Exact first divergence

Fresh full-route-neutral CPU traces4015/4016 cover3274–3278. Replay durations
23.730/23.144s. At3276 both variants enter FA54 near line80/cycle1060, but:

| Event |3955|4007|
|---|---|---|
| Sound-state setup sets07FE bit7 at8029 |126/384|79/1286|
| Driver checks BIT07FE at8146 |81/872|81/876|
| Branch |normal loop814B|busy return819A|
| Setup clears bit7 at8121 |129/1166|110/710|
| FA54→FA64 master clocks |13976|2356|

4007's entered call does not run sound processing:8146 BIT07FE,8149 BMI,
819A RTS. It nevertheless follows the scheduler's normal completion/publication
path, yielding a packet with zero original CPU APU writes and previous noise
volume34.3955 does three writes and advances that volume to33 before setup.
This accounts for packet2876/frame3276. It is not lost serial data.

The guard and setup lock/unlock sequences match the pinned original NES bytes:
source SHA `b95f8def04c0012604b7cc68cf4ed8f49b2dfe4beda6182051de4b2423bea7b1`.
In particular8146 is `2cfe07304fa207`. Both SNES cartridges retain it. The
initial hypothesis that this necessarily requires a scheduler retry is therefore
not established: the original engine deliberately has this busy-return path.
Preserving sound-state safety and establishing intended update cadence are
separate requirements.

## Full-route sparse audit

4017/4018 observe actual entry8146, accepted branch814B, return819A and request
entry8020. Each independently preserves all9,090 frames, input/state timeline
and native PCM against its exact same-core normal. No new core or emulated
memory access. The capture validates the relevant original NES and SNES bytes.

-3955:8268 complete original-driver calls, zero busy returns,230 setup requests.
-4007:8268 complete calls, two busy returns at3276 and3300,230 setup requests.
- Every normal/busy call, request and other-bank hook event is retained.
- Missing returns, nested calls, wrong return stack and censored traces fail;
  actual missing-return trace mutants are rejected in both arms. Two unit tests
  pass. These checks do not prove equal request IDs: that field is not logged.
- Fresh replay24.196/23.955s; totals29.201/28.904s including post-capture
  verification. No broad graphics/combat rerun was launched for this diagnosis.

The first collision is explained. The second is consistent with additional
source divergence, but the entire2551-packet difference and three-fewer-pulse
restart total are NOT fully attributed by counts alone. Matched original-NES
sound-request/update behavior and acoustic acceptance remain open. Keep4007
experimental and3955's stronger graphics qualification separate.

Next establish request identity/order and sound-update phase across the3300
collision and the3322 game-NMI-counter sample before choosing whether to adjust
native scheduling. Do not bypass the original guard to obtain matching totals,
or present a retry policy as faithful merely because it produces more updates.

[All busy/normal calls and first-collision instructions](http://127.0.0.1:8766/sound-busy-review-4019/)
· [Source/receive audit](http://127.0.0.1:8766/receiver-token-priority-source-review-4014/)
· [Audio issue6](https://github.com/struktured-labs/river-city-ransom-snes/issues/6).
