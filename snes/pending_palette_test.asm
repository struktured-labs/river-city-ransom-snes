.setcpu "65816"
.include "wram_clear.inc"
.a8
.i16
.segment "CODE"
reset:
    jml $C00000+start
start:
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
    lda #1
    sta $420D
    stz $2121
    ldx #256
@cgram:
    lda #$34
    sta $2122
    lda #$12
    sta $2122
    dex
    bne @cgram
    ldx #0
@seed:
    txa
    eor #SEED
    sta $0110,x
    eor #$55
    sta f:$7F3F00,x
    sta f:$7E5580,x
    inx
    cpx #32
    bne @seed
    rep #$20
    .a16
    lda #$1234
    ldx #0
@prepared:
    sta f:$7E5400,x
    sta f:$7E5500,x
    inx
    inx
    cpx #128
    bne @prepared
    sep #$20
    .a8
    lda #INITIALIZED
    sta $1C79
    lda #DEPTH
    sta $1C0A
    lda #BANK_GUARD
    sta $1C83
    lda #TASK
    sta $0100
    lda #GUARD
    sta $0107
    lda #FLAGS
    sta $003E
    lda #PENDING
    sta $1CE0
    lda #STATE
    sta $1CA0
    lda #ARMED
    sta $1CEB
    lda #ITERATION
    sta $1CE1
    lda #QUEUE_READ
    sta $06B6
    lda #QUEUE_WRITE
    sta $06B7
    lda #FADE_LEVEL
    sta $0692
.if PREVIEW_WRITE_HEAD
    lda #QUEUE_CONTROL
    sta $0545+((QUEUE_READ+2)&63)
.endif
    rep #$20
    .a16
    lda #$1E00
    tcd
    sep #$20
    .a8
.if INTEGRATED
    lda #$0F
    sta $2100
@wait_line:
    lda $213F
    lda $2137
    lda $213D
    cmp #<BEAM_LINE
    bne @wait_line
    lda $213D
    and #1
    cmp #>BEAM_LINE
    bne @wait_line
    jsr native_video
.else
    ldx #$1234
    ldy #$5678
    lda #$36
    sec
    clv
    jsl $C07000
    sta f:$7E6000
    php
    pla
    sta f:$7E6001
    rep #$20
    .a16
    txa
    sta f:$7E6002
    tya
    sta f:$7E6004
    tdc
    sta f:$7E6006
    tsc
    sta f:$7E6008
    sep #$20
    .a8
    phb
    pla
    sta f:$7E600A
.endif
    lda #$80
    sta $2100
    stz $2121
    ldx #0
@read_cgram:
    lda $213B
    sta f:$7E6200,x
    inx
    lda $213B
    and #$7F
    sta f:$7E6200,x
    inx
    cpx #512
    bne @read_cgram
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
.include "native_video.asm"
native_palette:
    .repeat 64, color
        .word (color * 509 + 17) & $7FFF
    .endrepeat
.segment "HEADER"
    .byte "RCR PENDING PAL TEST "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
