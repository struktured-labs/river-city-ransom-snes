; One production row conversion amid immutable queued staging snapshots.
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
    cpx #4096
    bcs :+
.ifdef SHADOW_XOR
.if SHADOW_XOR <> 0
    eor #SHADOW_XOR
.endif
.endif
    sta f:$7F2000,x
:
    inx
    cpx #8192
    bne @fill
    lda #MIRROR_MODE
    sta $1C18
    lda #PATTERN_HALF
    sta $1C20
    sta $1C78
    lda #ALIAS_STATE
    sta $1D00+(SOURCE_ROW ^ ALIAS_XOR)
    lda #1
    sta $1D00+SOURCE_ROW
    sta $1C79
    sta $1C85
    lda #SOURCE_ROW
    sta $1C76
    lda #$C0
    sta $0100
    rep #$20
    .a16
    lda #$1E00
    tcd
    jsr native_prepare
fused_test_return:
    sep #$20
    .a8
    phb
    pla
    bne fail
    rep #$20
    .a16
    tdc
    cmp #$1E00
    bne fail
    sep #$20
    .a8
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
    .byte "RCR FUSED ROW TEST   "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
