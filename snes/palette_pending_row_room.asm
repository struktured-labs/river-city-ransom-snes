; A8/X16, DB=0, DP=$1E00. Upper bound after existing VBlank/high-beam checks.
; Preserve the original forced-blank SEC/RTS entry in the caller.
.setcpu "65816"
.a8
.i16
.segment "CODE"
    lda $003E
    and #8
    bne pending
    lda $1C
    cmp #252
    bcs no
    sec
    rts
pending:
    lda $1C
    cmp #249
    bcs no
    sec
    rts
no:
    clc
    rts
