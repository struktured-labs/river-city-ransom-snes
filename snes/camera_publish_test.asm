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
    lda #44
    sta $F6
    lda #1
    sta $3D
    lda #42
    sta $1C94
    sta $1C97
    ; Check preservation of the descriptors and adjacent HUD/text entries.
    lda #127
    sta $1C93
    lda #35
    sta $1C96
    lda #45
    sta $1C99
    sep #$30
    .a8
    .i8
    sec
    xce
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
    .repeat DELAY_NOPS
        nop
    .endrepeat
    ldx #$56
    ldy #$78
    jsr camera_publish_safe
    php
    pla
    and #1
    sta f:$7E6000
    txa
    sta f:$7E6001
    tya
    sta f:$7E6002
    tsx
    txa
    sta f:$7E6003
    ; Read the helper's existing latched beam without relatching it. This
    ; gives the actual decision line even when DELAY_NOPS crossed a boundary.
    lda $213D
    sta f:$7E6006
    lda $213D
    and #1
    sta f:$7E6007
    lda $213F
    lda $2137
    lda $213D
    sta f:$7E6004
    lda $213D
    and #1
    sta f:$7E6005
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
.include "camera_publish_safe.inc"
.segment "HEADER"
.byte "RCR CAMERA SAFE TEST "
.byte $21,$00,$0B,$00,$01,$00,$00
.word $FFFF,0
.segment "VECTORS"
.word 0,0,irq,irq,irq,irq,0,irq
.word 0,0,irq,0,irq,irq,reset,irq
