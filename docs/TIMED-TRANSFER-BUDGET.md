# Integrated transfer budget — 4098 still fails broad acceptance

CPU trace4088 reproduces4084's full primary timeline/native PCM. During frames
1767–1770, the14audio waits cost78650/72420/73620/73846master clocks perframe,
about3.4–3.7ms. Each pair repeatedly enters full legacy envelope/sweep idle work.

4089 services full idle only on an actual Timer0 tick while waiting for a token;
the consumed tick is passed to the original receiver clock body3284. Holding
still services envelopes continuously.4095 additionally removes the duplicate
pre-arm idle call: normal command dispatch already services old-state idle, and
the explicit pre-arm timer-drain loop remains. Each variant passes192isolated
cases,202varied sequential packets,andfivebroken-codecontrols.

Integrated4098 SHA
`d4c66a178a1abbe0d33b2cc12bffe5a5ca9ebfabcd8f62b8ecf58c244ff07961`:

-Prefix4099 completes2581frames,6.171s replay/6.320s total.4100observes597school
 and65next-room intervals,alltwoframes. This did not qualify later scenes.
-Full4101 completes8910frames. Same-core4102primarytimeline/nativePCM exactly
 match. Full nativeDAC4750072stereoframes,peak6292,clipping0,maxstep4132.
-School597,alley455,park755intervals alltwoframes. Mall1758intervals include
 **12three-frame intervals: FAIL**. Firstslow interval3185–3188, camera255.
-All8506ready events retained;7149stable intervals and1356excluded intervals.
 Stable gaps14.724–33.833ms,median16.548ms. **No whole-route audio improvement
 claimed**. Source-to-sound onset, restart ordering and pop-free acceptance open.

The observer's in-process parser initially read a partially buffered CSV line.
After its confirmed terminal exit, finalizer analyzed the existing complete
files without replay or skipping rows, and reverified the entire primary capture.
Prior in-process trace hashes (including4100) become stale when stdio flushes
at exit; their derived metrics are not authoritative cached artifacts. The4102
finalized report and4103webreview bind the complete terminated traces. Future
capture tooling must flush host trace buffers before parsing/hashing, or analyze
in a parent process after child completion. No emulated timing flush is needed.

[Full native audio and candidate scenes](http://127.0.0.1:8766/integrated-timed-audio-review-4103/)
was rendered and visually inspected. No deployment or release promotion.
Next: trace mall3185–3188 and longest ready gap, including CPU production timing
and late-header policy. Do not infer matching encounters or NES-speed equivalence.
