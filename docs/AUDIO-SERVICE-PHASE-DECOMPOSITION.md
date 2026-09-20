# Residual audio jitter is visible before SPC transfer

Current experimental cartridge remains3695, SHA256
`60a73e42f287c3103b21751dca39cd37af1b3d7d31253da828b0979f855f636b`.
No new cartridge patch, default promotion or MiSTer deployment in this investigation.

Fresh capture `build/overflow-3526/audio-service-phases-3721` observes the
original FA54 entry and FA64 pre-RTS return, plus pending-service and early-helper
entry. All9091 primary timeline frames and native PCM exactly match the existing
same-core3706 control. Replay took27.584seconds. Actual source/core/cartridge
hashes and observer output are bound by `sound-service.json`.

Audit `build/overflow-3526/audio-service-audit-3722/report.json` pairs8156 complete
driver calls, retaining all transitions. No nested, missing, stack-mismatched or
terminal-censored call was accepted. Two unit tests cover exact decomposition
and five malformed-envelope cases.

The suspect region identified by the earlier SPC-completion diagnostic contains:

| CPU observer frame | Entry spacing (ms) | Execution-duration change (ms) | Return spacing (ms) |
| --- | ---: | ---: | ---: |
|2118|21.265|-0.100|21.165|
|2119|12.013|-0.012|12.002|
|2120|21.493|+2.124|23.617|
|2121|11.786|-1.212|10.574|
|2122|16.639|+0.327|16.965|

At2119 the driver starts at scanline80 and takes0.534ms. At2120 it starts at
scanline157 and takes2.658ms. The return-spacing identity is exact in master
clocks: entry spacing plus the change in execution duration equals return spacing.
Thus substantial irregularity exists upstream of SPC transfer; a downstream-only
explanation is insufficient for this CPU-side variation.

This does NOT yet directly join SPC packet1728 to that call: CPU observer frame
numbers and native PCM callback frame numbers are different clock-domain views.
Nor does it establish audible popping, incorrect original-driver work, or dropped
ticks. No smoothing, filtering or gain reduction was used.

Next: inspect the short2119–2121 instruction window, including4200 policy writes,
depth/mapper guards and deferred-service entry. Determine which critical section
prevents the scanline80 service on2120 and which driver path adds2.124ms. Only then
choose a scheduler/critical-section change. Preserve full-register safety and
graphics publication deadlines; keep original-speed/combat and physical audio
acceptance open.
