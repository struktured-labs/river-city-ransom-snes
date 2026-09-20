# Remaining3955 audio target: command acknowledgement

Fresh neutral CPU observation3988 covers8484–8487, including current worst
stable packet gap8485→8486 (20.857717ms). Full replay23.275s; exact complete
primary timeline/native PCM equality to3957. No sound or scheduling changes.

| Frame | Original driverFA54→FA64 | SenderD2BC→D2F9 | READY7D wait | CommandD7 wait |
| --- | ---: | ---: | ---: | ---: |
|8484|15592|29404|72|1616|
|8485|23022|22844|112|1814|
|8486|33198|39040|72|16176|
|8487|12726|20692|98|2488|

All values are elapsed master clocks, measured at instruction entry through
before the returning RTS. Wait calls runD253→D261; actual original poll bytes
atD253 are`a2ffffcd4021f005cad0f838601860`. Tables do not equate CPU wait time to
exclusive SPC execution. Other instructions, data-token waits and all frames
remain in the trace.

In8486 the CPU's READY wait is short, but commandD7 acknowledgement accounts
for16,176 of39,040 sender clocks. Individual data-token waits are:
0:3398,2:890,4:3332,6:930,8:838,10:904,12:838,14:904,16:3372,18:824,20:890,22:758.
The large command stall is distinct from the3934 optimization, which shortens
the data receiver's unmatched-token loop atSPC3530.

`tools/build_sweep_driver.py` describes separate idle poll/publication and
packet reception paths, but the current engine has subsequent guarded patches.
Its exact manifest/ROM, not that older generator alone, defines the current
code. Next observe which SPC work occupies the command wait before changing
handshake order, timers or CPU scheduling. Command-first polling or publication
changes are hypotheses, not implemented fixes or established causes.

Binding: `build/early-oam-live-half-worst-audio-3988/service-instructions.json`.
Trace: `build/early-oam-live-half-worst-audio-3988-instructions.csv`.
Native audio: [full3962 review](http://127.0.0.1:8766/early-oam-live-half-audio-review-3962/).
This does not prove audible popping, pop-free sound or original-NES fidelity.
