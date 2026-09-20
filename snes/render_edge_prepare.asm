; Replace only the transition1->2 STA. Adapter already masks NMI.
; Do not duplicate the existing synchronous startup/NMI-disabled path, and
; never recurse from inside the original game NMI. Preserve original A/P.
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
done:
    pla
    plp
    rts
