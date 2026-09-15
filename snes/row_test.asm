; Asset-free executed row-conversion oracle fixture. No DMA consumes staging.
.setcpu "65816"
.a8
.i16
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
    ldx #0
@clear:
    lda #0
    sta f:$7E0000,x
    sta f:$7F0000,x
    inx
    bne @clear
    ; Distinct tile/attribute data across all four nametables.
    rep #$20
    .a16
    ldx #0
@shadow:
    stx $00
    txa
    xba
    eor $00
    sep #$20
    .a8
    sta f:$7F2000,x
    rep #$20
    .a16
    inx
    cpx #4096
    bne @shadow
    sep #$20
    .a8
    ldx #0
    lda #1
@dirty:
    sta $1D00,x
    inx
    cpx #128
    bne @dirty
    lda #PATTERN_HALF
    sta $1C20
    lda #1
    sta $1C85
    lda #64
    sta $1C8B
    rep #$20
    .a16
    lda #$1E00
    tcd
@prepare:
    jsr native_prepare
    sep #$20
    .a8
    dec $1C8B
    beq @ready
    rep #$20
    .a16
    bra @prepare
@ready:
    .a8
    lda #1
    sta $1C60
    lda #$0F
    sta $2100
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
interrupt:
    rti
.include "native_prepare.asm"
.segment "HEADER"
    .byte "RCR ROW ORACLE TEST  "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
