; Follow-up to consumer_linear_scan: align odd starts with one scalar visit,
; not an eight-entry skip that stays odd and repeats fallback overhead.
.setcpu "65816"
.a16
.i16
.segment "CODE"
    rep #$20
    txa
    and #1
    bne scalar
    stx $1C
    tya
    clc
    adc $1C
    cmp #128
    bcc fallback
    lda #$0202
    jmp (entries,x)
fallback:
    sep #$20
    .a8
    cpx #121
    jmp $83A3
scalar:
    sep #$20
    .a8
    jmp $83D9
.a16
found:
    lda $1D00,x
    and #2
    bne :+
    inx
:
    txa
    sec
    sbc $1C
    sta $1C
    tya
    sec
    sbc $1C
    tay
    sep #$20
    .a8
    jmp $83D9
.a16
empty:
    lda #128
    sec
    sbc $1C
    sta $1C
    tya
    sec
    sbc $1C
    tay
    ldx #0
    cpy #0
    beq finish
    jmp $839E
finish:
    jmp $844F
entries:
    .repeat 64, pair
        .word search + pair*11
    .endrepeat
search:
    .repeat 64, pair
        bit a:$1D00 + pair*2
        beq :+
        ldx #pair*2
        jmp found
:
    .endrepeat
    jmp empty
