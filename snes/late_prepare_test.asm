.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.segment "CODE"
reset:
    sei
    clc
    xce
    rep #$38
    .a16
    lda #0
    tcd
    ldx #$1FFF
    txs
    sep #$20
    .a8
    pha
    plb
    stz $4200
    stz $420B
    stz $420C
    lda #$80
    sta $2100
    clear_wram_dma
    lda #4
    sta $2133
    lda #TRANSITION_STATE
    sta $1CA0
    ldx #0
@poison:
    txa
    sta $1D00,x
    sta f:$7E3000,x
    sta f:$7F2000,x
    inx
    cpx #256
    bne @poison
    rep #$20
    .a16
    lda #$1234
    tcd
    sep #$30
    .a8
    .i8
    sec
    xce
@blank:
    lda $4212
    bpl @blank
@visible:
    lda $4212
    bmi @visible
@target:
    lda $213F
    lda $2137
    lda $213D
    cmp #<TARGET_LINE
    bne @target
    lda $213D
    and #1
    cmp #>TARGET_LINE
    bne @target
    ldx #$56
    ldy #$78
    jsr late_prepare_allowed
    php
    pla
    and #1
    sta f:$7E6000
    txa
    sta f:$7E6001
    tya
    sta f:$7E6002
    phd
    pla
    sta f:$7E6003
    pla
    sta f:$7E6004
    tsx
    txa
    sta f:$7E6005
    lda #1
    sta $1C60
alive:
    lda $4212
    bmi alive
@blank:
    lda $4212
    bpl @blank
    inc $1C62
    bne alive
    inc $1C63
    bra alive
interrupt:
    rti
.include "late_prepare_helper.inc"
.segment "HEADER"
    .byte "RCR LATE PREP TEST  "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
