; Isolated alias snapshot/ABI oracle. No original game data or DMA.
.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.segment "CODE"
reset:
.ifdef FASTROM_TEST
    jml $C00000+fast_entry
fast_entry:
.endif
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
.ifdef FASTROM_TEST
    lda #1
    sta $420D
.endif
    lda #$80
    sta $2100
    clear_wram_dma
    ldx #0
@fill:
    rep #$20
    .a16
    stx $00
    txa
    xba
    eor $00
    sep #$20
    .a8
    sta f:$7E3000,x
    inx
    cpx #8192
    bne @fill
    lda #MIRROR_MODE
    sta $1C18
    lda #ALIAS_STATE
    sta $1D00+(SOURCE_ROW ^ ALIAS_XOR)
    lda #2
    sta $1D00+SOURCE_ROW
    rep #$20
    .a16
    lda #SOURCE_ROW
    sta $1E14
    lda #$1E00
    tcd
    sep #$20
    .a8
    lda #$81
    pha
    plb
    ldy #$3456
    jsr prepare_row_alias
alias_return:
    cpx #SOURCE_ROW
    beq :+
    jmp fail
:
.if ALIAS_STATE = 1
    cpy #$3040+(SOURCE_ROW ^ ALIAS_XOR)*64
.else
    cpy #$3456
.endif
    beq :+
    jmp fail
:
    php
    pla
    and #$30
    cmp #$20
    bne fail
    phb
    pla
    cmp #$81
    bne fail
    rep #$20
    .a16
    tdc
    cmp #$1E00
    beq :+
    sep #$20
    jmp fail
:
    sep #$20
    .a8
    lda $1D00+(SOURCE_ROW ^ ALIAS_XOR)
.if ALIAS_STATE = 1
    cmp #2
.else
    cmp #ALIAS_STATE
.endif
    bne fail
    lda #1
    sta $1C60
    bra ready
fail:
    sep #$20
    .a8
    lda #14
    sta $1C61
    lda #$EE
    sta $1C60
ready:
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
    .byte "RCR ALIAS WORD TEST  "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
