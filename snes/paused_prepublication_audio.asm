; Experimental pause-only scheduling. Enter by the displaced JSR publish_video
; in bank C0, E=1/A8/X8, interrupted A already saved by the native NMI.
.setcpu "65816"
.a8
.i8
.segment "CODE"
    lda a:$003F
    and #$20
    beq publish
    lda a:$0100
    and #$C0
    cmp #$C0
    bne publish
    lda a:$0107
    bmi publish
    lda a:$1CA0
    bne publish
    ; Never pre-service an in-flight retained camera iteration or old body.
    lda a:$1CE0
    ora a:$1CE1
    bne publish
    lda a:$1CFD
    beq service
    lda a:$1CFE
    cmp a:$1C04
    bne service
    lda a:$1CFF
    cmp a:$1C05
    beq publish
service:
    jsl $C15F00
publish:
    ; Tail-call displaced publisher with its original JSR return frame.
    jmp $8193
