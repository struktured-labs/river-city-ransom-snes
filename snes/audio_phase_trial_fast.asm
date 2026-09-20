; Preserve3661's service semantics, but keep inactive enable sites cheap and
; perform fallback after the bounded graphics publisher rather than before it.
.include "audio_phase_trial.asm"
.export fast_recover, after_publish
fast_recover:
    lda a:$1CA3
    bne active_recover
    lda a:$1C20
    and #$80
    rtl
active_recover:
    jml $C10000+recover
after_publish:
    jsl $C10000+drain
    jml $C17600
