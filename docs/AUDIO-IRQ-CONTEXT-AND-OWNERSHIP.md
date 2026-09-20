# Complete IRQ context and deferred sound ownership

Current experimental candidate3695:
`build/audio-phase-depth-game-3695/native-cpu.sfc`
SHA256 `60a73e42f287c3103b21751dca39cd37af1b3d7d31253da828b0979f855f636b`.
No deployment, default promotion, MiSTer, controller or OBS action occurred.

[Current audit and native audio](http://127.0.0.1:8766/audio-depth-review-3705/).
The page was rendered/inspected and its linked native WAV returnedHTTP200.
This report supersedes assumptions that the earlier IRQ trace covered flags,
bank/direct-page restoration or the intended return address.

## Complete pre-IRQ/post-RTI observer

Separate source-bound core3688 observes immediately before `S9xOpcode_IRQ` and
immediately after the original RTI executes. It records exact PB:PC, full A
(including B), X/Y/S, P including E, DP and DB. Lazy NZCV flags are combined
without calling the status-packing routine or modifying emulated state. There
are no emulated bus accesses, synchronization or added cycles. The expected
return PC is the actual interrupted PC, not a value inferred from the handler's
own saved stack. Build time17.875s; core SHA256
`40d53af3a8f99508fea77773274efa713ddedadaedb7debd7e95488b45d66aa9`.

Every capture has a fresh same-core unobserved control. That control separately
matches the old primary core's complete timeline and native PCM. Observed runs
then match their own controls exactly; cross-core equality is not substituted
for observer neutrality.

| Cartridge / route | Control / observation / audit | IRQs | Context result |
| --- | --- | --- | --- |
| Broken3665, pause |3691 /3694 /3699|657|All657 fail hidden A.high|
| Full-A repair3682, pause |3689 /3692 /3697|662|All pass|
| Full-A repair3682, park sweep |3690 /3693 /3698|4612|All pass|
| Ownership guard3695, pause |3700 /3703 /3704|663|All pass|

The audits reject missing/duplicated/censored events and deliberate damage to
each checked CPU field. Seven focused unit tests exercise context parsing,
fail-closed core insertion and early-enable detection. Direct critical-section
recovery and NMI/coroutine return paths are not IRQ events and still need their
own context checks. The long-route IRQ evidence belongs to3682, not3695.

## A second real integration defect

The full-A repair's executed instruction trace shows the real sound driver's
bank/APU adapters writing `$80` to4200 while the audio IRQ is still running.
The new IRQ service had not claimed the existing1C0A interrupt-depth guard.
The adapters therefore treated themselves as safe main-thread exits and
re-enabled NMI inside the owned sound service.

This is a verified premature-enable window, not a reproduced rare nested-NMI
crash. In the same1430–1445 window, sixteen actual IRQs contain59 premature
enables before the intended epilogue. The correct response is to keep the
existing guard active, not change original music counters or ignore nesting.

`tools/build_audio_phase_depth.py` inserts an11-byte replicated wrapper:
`INC $1C0A / JSL $C15F00 / DEC $1C0A / RTL`, and redirects the eight exact
deferred-service call sites. The opcode signature, parent hash and free helper
space are checked. This covers IRQ service, direct missed-timer recovery and
old-job fallback without manufacturing completed-audio tokens. No SPC engine,
graphics assets or source driver commands change.

Fresh3696 completes2537 pause/status frames. Instruction observation3701 is
neutral across the whole replay and PCM; its sixteen observed IRQs now contain
zero premature enables. Only the owning IRQ epilogue enables NMI. Review3705
retains all actual writes for both cartridges, rejecting the real unguarded
parent. Complete CPU-state observation3703 separately passes all663 pause IRQs.
Native onset3702 is still57 input-relative frames, matching the NES; delayed
and dead-sound controls fail. This does not establish waveform/pop equivalence.
Full unittest discovery passes1447 tests in22.970s; historical fixtures in that
suite are not a substitute for current-cartridge qualification.

## Next acceptance work

Run direct-recovery context checks (including caller flag policy and extra
stack depth) and requalify the guarded cartridge's longer route, actual rendered
scrolling, DMA, game cadence, sprite/CHR publication and audio discontinuities.
Investigate pause-route late fallbacks rather than equating balanced tick
counts with timely sound. Matched NES workload speed and controlled physical
audio remain open. Prior cartridge graphics passes are not inherited.
