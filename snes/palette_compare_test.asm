.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.segment "CODE"
reset:
    jml $C00000+entry
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
    ldx #$1FFF
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
    rep #$20
    .a16

.macro run_case target, result
    sep #$20
    .a8
    lda $0600
    and #$CF                  ; native A16/X16, every other flag varied
    pha
    rep #$20
    .a16
    lda #$BA5E
    ldx #$1259
    ldy #$BEEF
    plp
    jsr target
    php                       ; result may be A8 or A16
    rep #$20
    .a16
    sta result
    sep #$20
    .a8
    pla
    sta result+2
    stx result+3
    sty result+5
    phb
    pla
    sta result+7
    phd
    rep #$20
    .a16
    pla
    sta result+8
    tsx
    stx result+10
    lda $060C
    sta result+12
    cld
.endmacro
case_start:
    lda $0600
    and #$00FF
    sta $0606
    xba
    ora $0606
    eor #$A55A
    sta $0606
    ldx #0
@seed:
    txa
    eor $0606
    sta f:$7F3F00,x
    sta f:$7E5580,x
    inx
    inx
    cpx #32
    bne @seed
    lda $0601
    and #$00FF
    cmp #16
    beq @save_palettes
    asl
    tay
    lda $0600
    and #15
    tax
    lda #1
    cpx #0
    beq @flip
@shift:
    asl
    dex
    bne @shift
@flip:
    sta $0608
    tyx
    lda f:$7F3F00,x
    eor $0608
    sta f:$7F3F00,x
@save_palettes:
    ldx #0
@save:
    lda f:$7F3F00,x
    sta $0800,x
    lda f:$7E5580,x
    sta $0820,x
    inx
    inx
    cpx #32
    bne @save
    run_case original, $0700
    run_case optimized, $0720
    ldx #12
@registers:
    lda $0700,x
    cmp $0720,x
    bne failed
    dex
    dex
    bpl @registers
    ldx #0
@memory:
    lda f:$7F3F00,x
    cmp $0800,x
    bne failed
    lda f:$7E5580,x
    cmp $0820,x
    bne failed
    inx
    inx
    cpx #32
    bne @memory
    sep #$20
    .a8
    inc $0600
    beq :+
    rep #$20
    .a16
    jmp case_start
:
    .a8
    inc $0601
    lda $0601
    cmp #17
    beq complete
    rep #$20
    .a16
    jmp case_start
complete:
    .a8
    lda #1
    sta $0602
    sta $1C60
    bra idle_setup
failed:
    .a16
    stx $1C64
    sep #$20
    .a8
    lda #$FF
    sta $1C60
idle_setup:
    lda #0
    pha
    plb
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
.segment "CHANGED"
    .a16
    php
    pha
    lda #1
    sta $060C
    pla
    plp
    rts
.segment "MATCH"
    .a8
    php
    pha
    lda #0
    sta $060C
    pla
    plp
    rts
.segment "HOOK"
optimized:
    .incbin "hook.bin"
.segment "HELPER"
    .incbin "helper.bin"
.segment "HEADER"
    .byte "RCR PALETTE CMP TEST "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
