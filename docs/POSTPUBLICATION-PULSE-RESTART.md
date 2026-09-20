# Pulse restart ordering prototype

Follow-up: [actual DSP startup verification and Rival test deployment](PULSE-ONSET-RIVAL.md).
The following is the earlier prototype-stage report; its no-deployment decision
was superseded after actual voice-start verification.

September 18, 2026. Implemented and executed; **not deployed**. Rival was not
restarted or reconfigured. Current physical game remains `0956bd97b78f`.

[Native-rate A/B clips, including worse results](http://127.0.0.1:8766/postpublish-audio-review-1330/).

## Concrete finding

The live sweep publisher writes pulse pitch and volume near packet completion,
but the fast-reset handler issues DSP KON before those writes. Current-build
capture1320 exactly matches normal capture1169 across the complete8,861-frame
timeline and WAV. Its4,723,949 raw stereo DAC frames equal the delivered PCM;
all361,246 DSP writes satisfy the existing exact clock/phase checks.

Ordering audit1326 finds changed voice configuration written after restart and
before ready for1,564 of1,565 voice restarts. Many changed pitches arrive roughly
0.7–0.9ms after KON. This establishes register-write ordering, **not the precise
first audible sample's pitch or the cause of every reported pop**. Earlier
packet-delivery and same-pitch retrigger checks did not certify this property.

## Prototype

`build_postpublish_keyon.py` is an explicit, default-off builder. It retains the
merged reset/duty mask, merges duty-only requests, and flushes KON after the
live publisher sets SRCN/pitch/volume, immediately before the ready token.
The mask is then cleared. Verified unused padding at SPC$2F80 holds the helper,
after the existing triangle helper. Original instruction preimages are checked.

Engine length remains12,415 bytes. Only checked SPC bytes and ROM checksum
change; game CPU code, graphics, branding, sample directory and BRR data do not.
Candidate1321 SHA-256:
`fa882cb61138dac8a08bd3be7f71bf27153309f929e89d269764a7098e973d62`.

Complete candidate DSP capture1323 matches independent normal1322, including
the entire timeline and PCM. Audit1326 checks8,404 packets against actual
SPC receive instructions, verifies every expected merged reset/duty event,
and finds **zero** setup-after-restart cases among1,565 voice restarts. Idle
sweep writes after ready remain in the source trace and are not mistaken for
packet-setup failures. A deliberately delayed pitch observation is rejected;
this is a derived-trace control, not an executed damaged ROM. No clipping.

## Speed and scrolling regression

Main observer1324 and renderer observer1325 each match normal1322 exactly.
Cadence audit1327 passes without changing existing thresholds:

| Room | Complete stable loops | Ticks per loop / consecutive start interval |
| --- | ---: | --- |
| School0 | 598 | 2 / 2 frames |
| Alley1 | 1,746 | 2 / 2 frames |
| Mall2 | 475 | 2 / 2 frames |
| Park3 | 731 | 2 / 2 frames |

All3,550 stable loops pass. Park east/west have zero short1/3/4-frame equal-step
holds; longer14-frame stops remain. Excluded/censored loops remain explicit.
These are sampled regressions, not a new full-game or physical-speed claim.
Parent/candidate game RAM and some pictures differ despite equal route length;
the game runs are not used as identical-command audio comparisons.

## Identical-command audio comparison: mixed result

Player1328 changes only the SPC patch/checksum in existing player1257. Its
2,906-frame stream and2,512 packets are identical. Execution1329 preserves
every host-frame input/count/shadow. Both complete WAVs have1,741,101 samples
per channel at32,040Hz. There are301 differing callback boundaries, each by
one sample, retained in report1330. No alignment, resampling or gain fitting.

Across all227 reset/duty event callbacks, the full-mix maximum adjacent-sample
step improves84 times, is unchanged twice, and worsens141 times. The largest
event step increases3,335→3,431; the largest individual increase is1,845→3,075
at source frame2533. The review includes the three largest increases and
three largest decreases, with both unmodified native-rate clips for each.
A full-scale injected sample spike is detected.

These callback-wide mixed-channel steps include natural pulse/noise edges;
they do not identify perceptual clicks or prove the prototype sounds worse.
They also **do not justify calling it an audible-pop fix**. Therefore no Rival
deployment. Next isolate changed-pitch note onsets against an executed NES
reference and observe DSP voice startup, rather than promote the ordering
property alone or hide the unfavorable full-mix measurements.

Unit tests cover checked patch boundaries/length, branch destinations, both
voices' configuration registers, idle-versus-setup classification, packet
shadow repetition, disabled reset and full-scale signed sample arithmetic.
