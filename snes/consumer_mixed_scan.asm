; Fast OR reduction for empty groups, word-by-word location only in mixed
; groups. Avoid repeated group scans without slowing the all-empty finish.
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
    lda $1D00,x
    ora $1D02,x
    ora $1D04,x
    ora $1D06,x
    and #$0202
    beq empty8
    lda #$0202
    bit $1D00,x
    bne found0
    bit $1D02,x
    bne found2
    bit $1D04,x
    bne found4
    ; The group reduction guarantees the fourth pair is ready here.
    bra found6
empty8:
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
    jmp $83D7                 ; verified LDA $1D00,X, not its operand
finish:
    jmp $844F
