# Why the length-expiry diagnostic fails, and its RCR scope

The diagnostic is not repeatedly reloading the note: `bringup.asm` clears
packet event flags after each transfer, and only explicit start/restart/pitch
events set them. Pulse control $9F has halt clear. The earlier and current
length-expiry captures all sustain their active phases rather than expiring.

The pinned upernes host's `.deps/upernes/source/asm/Sound.asm` calls
`emulate_length_counter` from `SoundAPURegUpdate`. That CPU routine performs
length reload/countdown and constructs the enable mask before transferring
to the SPC. The standalone Memblers SPC does not supply general length
expiry. Our eligibility latch preserves disable/reload ordering but does not
implement that countdown. Its misleading comment claiming the SPC owns
expiry has been corrected. No partial frame-based countdown was added.

The current route does not exercise a running length counter at received
packet boundaries. `build/data-first-long-length-usage-01.json` validates all
169280 received bytes against CPU sends and classifies all 7360 packets:

| Channel | Enabled, halted | Enabled, running | Disabled |
| --- | ---: | ---: | ---: |
| Pulse 1 | 6966 | 0 | 394 |
| Pulse 2 | 6972 | 0 | 388 |
| Triangle | 6972 | 0 | 388 |
| Noise | 6972 | 0 | 388 |

The classifier uses pulse/noise bit 5 and triangle bit 7, with an explicit
unit control for their difference and disabled channels. All 117 Python
tests pass. Raw CPU control writes in this trace are also halt-set except
zero initialization writes to pulse/noise controls; triangle writes are
exclusively $80/$81. This does not certify other routes or sub-packet timing.

General length expiry remains a documented failed feature. It is not
established as the cause of popping in this route. The current retained ROM
remains `audio-data-first-02`; no executable code changed or hardware was
reloaded during this investigation.
