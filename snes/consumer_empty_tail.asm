; Preserve mixed-group search, but finish scalar misses locally instead of
; bouncing through the cartridge's scalar consumer and re-entering this helper.
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
    ; Byte-wide read is essential at127: do not read the CHR job flags.
    sep #$20
    .a8
    lda $1D00,x
    and #2
    bne ready
    rep #$20
    .a16
    inx
    cpx #128
    bcc :+
    ldx #0
:
    dey
    beq finish
    jmp loop
ready:
    .a8
    jmp $83D7
finish:
    jmp $844F
