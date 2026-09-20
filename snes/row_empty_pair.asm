; A16/X16/Y16, DB=0, DP=$1E00; first eight rows already have no ready bit.
; Visit a second eight-row group only within both ring and remaining budget.
.setcpu "65816"
.a16
.i16
.segment "CODE"
    cpx #113
    bcs skip8
    cpy #16
    bcc skip8
    lda $1D08,x
    ora $1D0A,x
    ora $1D0C,x
    ora $1D0E,x
    and #$0202
    bne skip8
    txa
    clc
    adc #16
    tax
    cpx #128
    bcc :+
    ldx #0
:
    tya
    sec
    sbc #16
    tay
    beq finish
    jmp $839E
skip8:
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
    jmp $839E
finish:
    jmp $844F
