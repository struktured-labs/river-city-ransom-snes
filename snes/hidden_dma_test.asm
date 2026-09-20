; Asset-free, single real publisher invocation and full VRAM readback.
.setcpu "65816"
.a8
.i16
.ifndef CHR_BYTES
    CHR_BYTES = 2048
.endif
.ifndef ROW_START
    ROW_START = 0
.endif
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
    lda #$80
    sta $2115
    ldx #$1000
    stx $2116
.if .defined(EXPERIMENTAL_PLANAR_ROWS) .or .defined(EXPERIMENTAL_HIDDEN_ROW_RUN)
    ldx #$2000
.else
    ldx #$1800
.endif
@clear_vram:
    stz $2118
    stz $2119
    dex
    bne @clear_vram
    ldx #0
@rows:
    lda #3
    sta $1D00,x
    lda #2
    sta $1E80,x
    inx
    cpx #128
    bne @rows
.ifdef QUEUE_GAP
    lda #1
    sta $1D00+QUEUE_GAP
.endif
    rep #$20
    .a16
    ldx #0
@staging:
    txa
    eor #$5AA5
    sta f:$7E3000,x
    inx
    inx
    cpx #8192
    bne @staging
    ldx #0
    lda #$A55A
@chr:
    sta f:$7E7000,x
    inx
    inx
    cpx #2048
    bne @chr
    lda #$7000
    sta $1500
    lda #$1000
    sta $1504
    lda #CHR_BYTES
    sta $1506
    lda #$1E00
    tcd
    sep #$20
    .a8
    lda #$7E
    sta $1502
    lda #1
.if CHR_BYTES <> 0
    sta $1D80
.endif
    sta $1C79
    lda #ROW_START
    sta $1C74
    lda #TRANSITION_STATE
    sta $1CA0
    lda #$18
    sta $1C21
    ; Start with display enabled: the transition publisher must force blank.
    lda #$0F
    sta $2100
@visible:
    lda $4212
    bmi @visible
.if TRANSITION_STATE = 0
@vblank:
    lda $4212
    bpl @vblank
.endif
    jsr native_video
    ; Read only after the actual production write has finished.
    lda #$80
    sta $2100
    sta $2115
    ldx #$1000
    stx $2116
    rep #$20
    .a16
    lda $2139
    ldx #0
@readback:
    lda $2139
    sta f:$7E8000,x
    inx
    inx
.if .defined(EXPERIMENTAL_PLANAR_ROWS) .or .defined(EXPERIMENTAL_HIDDEN_ROW_RUN)
    cpx #$4000
.else
    cpx #$3000
.endif
    bne @readback
    sep #$20
    .a8
    lda #1
    sta $1C60
@wait_visible:
    lda $4212
    bmi @wait_visible
@wait_blank:
    lda $4212
    bpl @wait_blank
    inc $1C62
    bne @wait_visible
    inc $1C63
    bra @wait_visible
interrupt:
    rti
.include "native_video.asm"
.segment "HEADER"
    .byte "RCR HIDDEN DMA TEST  "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
