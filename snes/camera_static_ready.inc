; A8, caller has already checked native transition state. X/Y/DP/DB intact.
; Carry is readiness, not a request to skip or synthesize an original NMI.
camera_static_ready:
    lda a:$0100
    and #$C0
    cmp #$C0
    bne @not_ready
    lda a:$0107
    bmi @not_ready
    lda a:$003F
    and #$20
    bne @not_ready
    lda a:$003E
    and #$82
    bne @not_ready
    lda a:$0692
    cmp #4
    bne @not_ready
    sec
    rts
@not_ready:
    clc
    rts
