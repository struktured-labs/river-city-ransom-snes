.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.segment "CODE"
reset:
    jml SOURCE_BANK*$10000+entry
entry:
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
    lda #1
    sta $420D
    lda #$80
    sta $2100
    clear_wram_dma
    lda #SOURCE_BANK-$40
    pha
    plb
    rep #$30
    .a16
    .i16
    ldx #$01FF
    txs
case_start:
    sep #$20
    .a8
    ldx $1800
    lda f:$C90006,x
    sta $1810
    ldy #0
@fill:
    tya
    eor $1810
    sta $0800,y
    sta $0900,y
    sta $0A00,y
    sta $0B00,y
    sta $0C00,y
    sta $0000,y
    sta $0545,y
    and #3
    ora #8
    sta $1000,y
    sta $1100,y
    iny
    cpy #256
    bne @fill
    lda f:$C90000,x
    sta $21
    lda f:$C90001,x
    sta $20
    lda f:$C90002,x
    sta $1811
    lda f:$C90003,x
    sta $1812
    lda f:$C90005,x
    sta $1A
    lda #$10
    sta $1B
    rep #$20
    .a16
    lda f:$C90004,x
    xba
    sep #$20
    .a8
    sec
    xce
    .i8
    lda $1812
    pha
    plp
    ldx $1811
    jsr $C2C3
    sta $1840
    php
    pla
    sta $1844
    stx $1842
    sty $1843
    xba
    sta $1841
    tsx
    stx $1845
    phb
    pla
    sta $1847
    clc
    xce
    rep #$30
    .a16
    .i16
    cld
    tsc
    xba
    sep #$20
    .a8
    sta $1846
    rep #$20
    .a16
    tdc
    sta $1848
    ldx $1802
    sep #$20
    .a8
    ldy #0
@record:
    lda $0000,y
    sta f:$7F0000,x
    lda $0545,y
    sta f:$7F0100,x
    inx
    iny
    cpy #256
    bne @record
    ldx $1802
    .repeat 10,i
        lda $1840+i
        sta f:$7F0200+i,x
    .endrepeat
    rep #$20
    .a16
    lda $1800
    clc
    adc #8
    sta $1800
    lda $1802
    clc
    adc #1024
    sta $1802
    inc $1804
    lda $1804
    cmp #CASES
    beq @done
    jmp case_start
@done:
    sep #$20
    .a8
    lda #1
    sta $1C60
@visible:
    lda $4212
    bmi @visible
@blank:
    lda $4212
    bpl @blank
    inc $1C62
    bne @visible
    inc $1C63
    bra @visible
.i8
.include "column_fetch.inc"
interrupt:
    rti
.segment "ORIGINAL"
.ifdef OPTIMIZED
    jmp native_column_fetch
    .res 29,$EA
.else
    .byte $a4,$21,$b1,$1a,$85,$1e,$c8,$b1,$1a,$85,$1f,$a4,$20,$b1,$1e,$9d,$45,$05,$e8,$20,$06,$c5,$e6,$21,$e6,$21,$a5,$21,$c9,$30,$90,$e0
.endif
.assert * = $C2E3, lderror, "Column return moved"
    rts
.segment "WRAP"
    txa
    and #$3F
    tax
    rts
.segment "HEADER"
    .byte "RCR COLUMN FETCH     "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
