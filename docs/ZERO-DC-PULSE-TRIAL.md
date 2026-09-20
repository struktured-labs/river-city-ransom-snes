# Zero-DC pulse waveform trial — scoped qualification

**Follow-up: [recorded-command replay rejects promotion](DC-PULSE-COMMAND-REJECTION.md).**
Four of eleven fixed gameplay-context windows have19–44% larger absolute
steps, despite the scoped checks below passing. Keep this as an offline
experiment; do not deploy it as the popping fix.

Candidate `build/dc-pulse-trial-2319`, ROM SHA
`8864cdaec7f63ba335e857c69b8d63c5efe52121fb56eb51a168b0b891917902`,
SPC SHA `d05c1194d2cb98f83d0eff16f68eed6a180619121498fe54d1eaf0408cea8dab`,
is **offline and default-off**. Parent is the current compact-pair speed
candidate2242, not Rival's regular1699 plus splash2089 build.

[Native audio and full qualification](http://127.0.0.1:8766/dc-pulse-review-2340/).
All four aggregate scoped gates pass. This is not a claim that physical
popping, all slowdown or the full game's scrolling is fixed.

## Actual implementation

The four16-sample BRR pulse loops retain their header, range, filter, lengths,
phase and duty pattern. Their two levels become an exact affine transform:
`new = (old - mean(old)) * 8/9`. Each new loop sums to zero.
Direct GAIN31→35 compensates AC span9→8; ideal AC ratio is280/279, or+0.3584%.
Both initialization and active-note gain restoration sites are changed.
Exactly32 SPC bytes change; other ROM changes are only the checksum. No
instruction counts, game CPU code, pitch, envelope/reset rules or graphics change.
This does not implement a complete NES analog output filter or repair the
legacy duty3 waveform's phase/polarity relative to the NES.

## Executed evidence

- Eight held pulse2 cases, both pitches and all duties: all existing NES
  transient bounds now pass. Fixed-window AC RMS stays approximately+0.36%;
  mean bias falls by more than95% within the defined finite-window allowance.
- Same-core normal/observed fixture pairs verify32 versus8 restarts, with no
  wrong first pitch or stale nonzero onset. The suppressed control removes
  only the24 periodic resets, not the initial notes.
- Executed wrong-active-gain control2334/2335 loses approximately11% AC level
  and fails the unchanged ±1% level gate. Its samples remain centered, showing
  why centering or a transient pass alone is insufficient.
- Full route: all9,225 non-audio game-state/image/timing rows and callback
  sample boundaries equal parent2258 exactly. Each same-core observer is
  neutral and its raw DAC equals delivered PCM.
- All371,584 actual DSP writes preserve clocks and values except the expected
  16,775 direct-gain writes. All ready clocks match.8,783 packets/202,009 bytes
  arrive intact;1,623 restarts have no late configuration. No clipping.
- Fresh host-isolated noise and triangle captures each retain all9,225
  non-audio rows and are sample-identical between parent and trial.
-1,111 unit tests pass (`/tmp/rcr-tests-dc-pulse-2341.log`); nine targeted
  DC/reference tests cover patch preimages, centering, all four gain sites,
  active-only negative control, quiet-signal rejection and DSP-clock mutation.

## Important retained regressions and limits

Absolute maximum restart steps do **not** all shrink:

| Period | Duty | Parent | Trial |
| --- | --- | ---: | ---: |
| $00FD | 0 | 2307 | 2885 |
| $00FD | 1 | 2309 | 3125 |
| $00FD | 2 | 2307 | 2084 |
| $00FD | 3 | 2309 | 1044 |
| $06C6 | 0 | 2309 | 2885 |
| $06C6 | 1 | 2309 | 3125 |
| $06C6 | 2 | 1845 | 2083 |
| $06C6 | 3 | 2309 | 1044 |

Centering raises asymmetric waveform peaks. The previously failing relative
step bound therefore improves without guaranteeing a smaller absolute edge.
The low/duty3 case from the physical command context does improve, but this
synthetic tone is not a replay of the whole physical incident. Previous
channel-split evidence implicated noise at8/11 selected replay edges; those
noise samples are intentionally unchanged here. No subjective approval,
physical pop-free certification or deployment has occurred.

Earlier pilot2314 omitted active gain restoration and was simply quieter.
Its historical builder binding was superseded during correction; it is
retained as exploration, not qualification. Fresh executed2334/2335 supplies
the authenticated negative control instead.

Next: replay the exact retained physical command episode with this engine,
inspect the same fixed event windows without timing/gain fitting, then test
any credible improvement through the physical capture chain. Do not present
isolated-tone gates as proof of the user's gameplay-audio complaint being fixed.
