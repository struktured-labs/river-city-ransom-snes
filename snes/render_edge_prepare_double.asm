; Bounded two-pass variant of render_edge_prepare.asm. Same guards and ABI.
.setcpu "65816"
.a8
.i8
.segment "HELPER"
entry:
    sta $1CA0
    php
    pha
    lda $1C0A
    bne done
    lda $1C79
    beq done
    lda $1C20
    bpl done
    jsl $C00000+PREPARE_BRIDGE
    jsl $C00000+PREPARE_BRIDGE
done:
    pla
    plp
    rts
