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
    lda #1
    sta $420D
    clear_wram_dma
    ldx #$02FF
poison:
    lda #$5A
    sta a:$1B00,x
    dex
    bpl poison
    lda #<ADDRESS
    sta a:$1B20
    lda #>ADDRESS
    sta a:$1B21
    lda #VALUE
    sta a:$1B22
    lda #OLD_CTRL
    sta a:$1C20
    lda #LATCH
    sta a:$1C25
    lda #$20
    sta a:$1C27
    lda #$1F
    sta a:$1C26
    lda #0
    sta a:$1C18
    sta a:$1C06
    sta a:$1C60
    sta a:$1C61
    sta a:$1C62
    sta a:$1C63
    lda #1
    sta a:$1C0A
    rep #$20
    .a16
    lda #$1234
    tcd
    sep #$30
    .a8
    .i8
    lda #$83
    pha
    plb
    sec
    xce
    ldx #STACK
    txs
    lda #FLAGS
    pha
    plp
    ldx #$A6
    ldy #$59
    lda #$57
    jml BANK*$10000+run
run:
    jsl BANK*$10000+ENTRY
    sta f:$7E6000
    php
    pla
    sta f:$7E6002
    xba
    sta f:$7E6001
    xba
    txa
    sta f:$7E6003
    tya
    sta f:$7E6004
    tdc
    sta f:$7E6005
    xba
    sta f:$7E6006
    xba
    phb
    pla
    sta f:$7E6007
    tsx
    txa
    sta f:$7E6008
    cld
    lda #1
    sta a:$1C60
alive:
    lda $4212
    bmi alive
blank:
    lda $4212
    bpl blank
    inc a:$1C62
    bne alive
    inc a:$1C63
    bra alive
.segment "HEADER"
    .byte "RCR PPU REGISTER TEST"
    .byte $31,$00,$0B,$00,$01,$00,$00
    .word $FFFF,$0000
.segment "VECTORS"
    .word 0,0,reset,reset,reset,reset,reset,reset
    .word 0,0,reset,0,reset,reset,reset,reset
