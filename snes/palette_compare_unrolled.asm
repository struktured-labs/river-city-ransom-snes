; Native A16/X16 palette comparison. Long addresses, no scratch or new writes.
; Preserve the exact first mismatching word, X offset and CMP flags at exit.
.setcpu "65816"
.a16
.i16
.segment "CODE"
palette_compare_unrolled:
    .repeat 16, word
        lda f:$7F3F00+word*2
        cmp f:$7E5580+word*2
        beq :+
        php
        ldx #word*2
        plp
        jmp CHANGED
:
    .endrepeat
    ldx #32
    cpx #32
    sep #$20
    jmp SPRITES
