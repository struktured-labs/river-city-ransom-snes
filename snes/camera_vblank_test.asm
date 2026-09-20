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
    lda #4
    sta $2133
    lda #1
    sta $1C79
    sta $1D80
    lda #TASK_VALUE
    sta $0100
    lda #TRANSITION_VALUE
    sta $1CA0
    lda #44
    sta $F6
    lda #1
    sta $3D
    lda #42
    sta $1C94
    sta $1C97
    lda #127
    sta $1C93
    lda #35
    sta $1C96
    lda #45
    sta $1C99
    ; One legal 2 KiB transfer consumes the budget and makes final_room
    ; refuse the optional final batch. No original game assets are needed.
    rep #$20
    .a16
    lda #$6000
    sta $1500
    lda #$0800
    sta $1506
    sep #$20
    .a8
    lda #$7E
    sta $1502
blank:
    lda $4212
    bpl blank
visible:
    lda $4212
    bmi visible
target:
    lda $213F
    lda $2137
    lda $213D
    cmp #<TARGET_LINE
    bne target
    lda $213D
    and #1
    cmp #>TARGET_LINE
    bne target
.ifdef DELAY_NOPS
    .repeat DELAY_NOPS
        nop
    .endrepeat
.endif
    rep #$20
    .a16
    lda #$1E00
    tcd
    sep #$20
    .a8
    jsr native_video
    lda $213F
    lda $2137
    lda $213D
    sta f:$7E6000
    lda $213D
    and #1
    sta f:$7E6001
    rep #$20
    .a16
    tdc
    sta f:$7E6002
    tsc
    sta f:$7E6004
    sep #$20
    .a8
    phb
    pla
    sta f:$7E6006
    lda #1
    sta $1C60
alive:
    lda $4212
    bmi alive
wait_blank:
    lda $4212
    bpl wait_blank
    inc $1C62
    bne alive
    inc $1C63
    bra alive
irq:
    rti
.include "native_video.asm"
.segment "HEADER"
.byte "RCR CAMERA VBLANK    "
.byte $21,$00,$0B,$00,$01,$00,$00
.word $FFFF,0
.segment "VECTORS"
.word 0,0,irq,irq,irq,irq,0,irq
.word 0,0,irq,0,irq,irq,reset,irq
