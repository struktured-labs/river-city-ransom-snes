; Scan each flag word once; locate its first ready byte without re-reading
; the whole eight-entry group for each scalar miss. A16/X16/Y16, DB0, DP1E00.
; Unlike suffix unrolling, partial budgets and odd starts use the same path.
.setcpu "65816"
.a16
.i16
.segment "CODE"
    rep #$20
loop:
    cpx #121
    bcs scalar
    cpy #8
    bcc scalar
    lda #$0202
    bit $1D00,x
    bne found0
    bit $1D02,x
    bne found2
    bit $1D04,x
    bne found4
    bit $1D06,x
    bne found6
    txa
    clc
    adc #8
    tax
    cpx #128
    bcc :+
    ldx #0
:
    tya
    sec
    sbc #8
    tay
    beq finish
    bra loop
found6:
    inx
    inx
    dey
    dey
found4:
    inx
    inx
    dey
    dey
found2:
    inx
    inx
    dey
    dey
found0:
    lda $1D00,x
    and #2
    bne scalar
    inx
    dey
scalar:
    sep #$20
    .a8
    jmp $83D9
finish:
    jmp $844F
