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
    ldx #$01FF
    txs
    rep #$20
    .a16
    lda #DIRECT_PAGE
    tcd
    sep #$20
    .a8
    lda #DATA_BANK
    pha
    plb
    sec
    xce
    .i8

.macro run_case target, result
    .local fill
    ldx #0
fill:
    txa
    eor $0601
    sta $0200,x
    inx
    bne fill
    lda $0600
    sta $052D
    lda #$A5
    xba
    lda $0601
    pha
    lda #$3C
    ldx #$59
    ldy $0601
    plp
    jsr target
    sta result
    php
    pla
    sta result+1
    stx result+2
    sty result+3
    xba
    sta result+4
    tsx
    stx result+5
    phd
    pla
    sta result+6
    pla
    sta result+7
    phb
    pla
    sta result+8
    lda $052D
    sta result+9
    cld
.endmacro
case_start:
    run_case original, $0700
    ldx #0
@save:
    lda $0200,x
    sta $0800,x
    inx
    bne @save
    run_case optimized, $0710
    ldx #9
@registers:
    lda $0700,x
    cmp $0710,x
    bne failed
    dex
    bpl @registers
    ldx #0
@memory:
    lda $0200,x
    cmp $0800,x
    bne failed
    inx
    bne @memory
    inc $0600
    inc $0600
    inc $0600
    inc $0600
    beq :+
    jmp case_start
:
    inc $0601
    beq :+
    jmp case_start
:
    lda #1
    sta $0602
    sta $1C60
    bra idle
failed:
    stx $1C61
    lda #$FF
    sta $1C60
idle:
    lda $4212
    bmi idle
@blank:
    lda $4212
    bpl @blank
    inc $1C62
    bne idle
    inc $1C63
    bra idle
interrupt:
    rti
.segment "ORIGINAL"
original:
    .incbin "original.bin"
.segment "HOOK"
optimized:
    .incbin "hook.bin"
.segment "HELPER"
    .incbin "helper.bin"
.segment "HEADER"
    .byte "RCR HIDE TAIL TEST   "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
