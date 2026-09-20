; Isolated native publisher trampoline, A8/X16, DB=0, DP=$1E00.
; Entered by JMP from $8457. Preserve transition state if final DMA admission
; fails; transition_ready may clear it after draining all required graphics.
.setcpu "65816"
.segment "CODE"
.a8
.i16
    lda $1CA0
    pha
    jsr $86E6
    jsr $86C8
    bcs admitted
    pla
    sta $1CA0
    rts
admitted:
    pla
    jmp $8460
