; One call per original main iteration, immediately before its two-tick wait.
; Never execute the record copy after both game ticks have already elapsed.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export camera_idle_log
camera_idle_log:
    php
    clc
    xce
    rep #$30
    .a16
    .i16
    pha
    phx
    phy
    phb
    sep #$20
    .a8
    cld
    lda #0
    pha
    plb
    lda a:$010B
    cmp #2
    bcs done
    ; Read both halves and leave the latch reader complete on every branch.
    lda a:$213F
    lda a:$2137
    lda a:$213D
    tax
    lda a:$213D
    and #1
    bne done
    txa
    cmp #194
    bcs done
    jsr $E000
done:
    plb
    rep #$30
    .a16
    .i16
    ply
    plx
    pla
    sep #$30
    .a8
    .i8
    sec
    xce
    plp
    rtl
