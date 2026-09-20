; Camera tail only, E=1/A8, NMI masked, original P/A already saved.
; Preserve X/Y/DP/DB/SP. Keep late work owned by the existing pending slot;
; interrupt exits still perform exactly-once fallback. Never clear $4210 here.
; Experimental early cutoff: the observed 55,518-clock pass needs ~41 lines.
; Before194 leaves >46 lines until overscan VBlank240. This is NOT a proven
; worst-case producer bound. Full-route and generation checks remain required.
second_tick_prepare_camera:
    lda a:$1B80
    beq @done
    lda $213F
    lda $2137
    lda $213D
    pha
    lda $213D
    and #1
    bne @late_high
    pla
    cmp #194
    bcs @done
    jmp second_tick_prepare_service
@late_high:
    pla
@done:
    rts
