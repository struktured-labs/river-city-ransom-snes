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
    ldx #0
ring:
.if UNCHANGED
    lda #0
.else
    txa
    eor #$A5
.endif
    sta a:$0545,x
    inx
    cpx #64
    bne ring
    ldx #0
dirty:
    txa
    and #3
    sta a:$1D00,x
    inx
    cpx #128
    bne dirty
    lda #MIRROR
    sta a:$1C18
    lda #STRIDE
    sta a:$1C20
    lda #<PPUADDR
    sta a:$1C26
    lda #>PPUADDR
    sta a:$1C27
    lda #1
    sta a:$1C0A
    lda #$FC
    sta a:$1C09
    rep #$20
    .a16
    lda #$1234
    tcd
    sep #$30
    .a8
    .i8
    lda #$82
    pha
    plb
    sec
    xce
    ldx #$FF
    txs
    lda #FLAGS
    pha
    plp
    ldx #RINGINDEX
    ldy #COUNT
    lda #$57
    jml BANK*$10000+run
run:
    jsr ENTRY
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
    .byte "RCR RING STRIDE TEST "
    .byte $31,$00,$0B,$00,$01,$00,$00
    .word $FFFF,$0000
.segment "VECTORS"
    .word 0,0,reset,reset,reset,reset,reset,reset
    .word 0,0,reset,0,reset,reset,reset,reset
