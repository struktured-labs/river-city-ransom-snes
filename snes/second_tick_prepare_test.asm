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
    .include "setup.inc"
    rep #$20
    .a16
    lda #$1234
    tcd
    sep #$30
    .a8
    .i8
    sec
    xce
    ldx #$56
    ldy #$78
.if ACTION < 3
    jsr second_tick_prepare
.endif
.if ACTION = 1 .or ACTION = 3
    jsr second_tick_prepare_service
.elseif ACTION = 2 .or ACTION = 4
    jsr second_tick_prepare_fallback
.endif
    txa
    sta f:$7E6000
    tya
    sta f:$7E6001
    phd
    pla
    sta f:$7E6002
    pla
    sta f:$7E6003
    phb
    pla
    sta f:$7E6004
    tsx
    txa
    sta f:$7E6005
    lda #1
    sta a:$1C60
alive:
    lda $4212
    bmi alive
@blank:
    lda $4212
    bpl @blank
    inc a:$1C62
    bne alive
    inc a:$1C63
    bra alive
video_prepare_bridge:
    inc a:$1BA0
    rtl
interrupt:
    rti
.include "second_tick_prepare.inc"
.segment "HEADER"
    .byte "RCR TICK TWO TEST    "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
