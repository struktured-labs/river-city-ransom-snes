; Diagnostic coverage gate. Off paths still send audio via the original code.
.setcpu "65816"
.a8
.i16
.segment "CODE"
.export gated_frame, recorded, unrecorded
gated_frame:
    lda a:$0100
    cmp #$C0
    bne unrecorded
    lda a:$0692
    cmp #4
    bne unrecorded
    lda a:$1CA0
    bne unrecorded
    lda a:$1C21
    and #8
    beq unrecorded
    lda a:$003E
    and #$82
    bne unrecorded
    lda a:$0107
    bmi unrecorded
    lda a:$003F
    and #$20
    bne unrecorded
recorded:
    jmp $E080
unrecorded:
    jmp spc_frame
