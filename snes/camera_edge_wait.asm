; Experimental late camera boundary. Preserve A (including B), X and P.
; Do not create an interrupt or advance a tick: allow the imminent native
; edge to arrive before entering the existing masked handoff.
.setcpu "65816"
.a8
.i8
.segment "CODE"
    php
    pha
    phx
    lda a:$1C0A
    ora a:$1C83
    bne done
    lda a:$1C20
    bpl done
sample:
    lda a:$213F
    lda a:$2137
    lda a:$213D
    tax
    lda a:$213D
    and #1
    bne done
    cpx #232
    bcc done
    cpx #240
    bcc sample
done:
    plx
    pla
    plp
    jmp $7BE0
