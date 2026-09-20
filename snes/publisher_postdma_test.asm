.setcpu "65816"
.include "wram_clear.inc"
.segment "CODE"
.a8
.i16
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
    lda #TRANSITION
    sta $1CA0
    lda #3
    sta $1D00
    sta $1D7F
    rep #$20
    .a16
    lda #$1E00
    tcd
    lda #ROWS*64
    sta $1E
    sep #$20
    .a8
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
    ldx #CURSOR
    ldy #$1234
    rep #$20
    .a16
    jml BANK*$10000+invoke
invoke:
    jsr HELPER
    php
    sep #$20
    .a8
    pla
    sta f:$7E6008
    rep #$20
    .a16
    txa
    sta f:$7E6000
    tya
    sta f:$7E6002
    tdc
    sta f:$7E6004
    tsc
    sta f:$7E6006
    sep #$20
    .a8
    phb
    pla
    sta f:$7E6009
    lda #1
    sta a:$1C60
alive:
    lda $4212
    bmi alive
wait_blank:
    lda $4212
    bpl wait_blank
    inc a:$1C62
    bne alive
    inc a:$1C63
    bra alive
.segment "NEXT"
    .a16
    .i16
    ; Production prefix increments the last transferred row to next cursor.
    inx
    cpx #128
    bcc :+
    ldx #0
:
    lda #1
    sta f:$7E6010
    rts
.segment "FINISH"
    lda #2
    sta f:$7E6010
    rts
.segment "HEADER"
    .byte "RCR POSTDMA TEST    "
    .res 1,0
    .byte $31,$00,$0B,$00,$01,$00,$00
    .word $FFFF,$0000
.segment "VECTORS"
    .word 0,0,reset,reset,reset,reset,reset,reset
    .word 0,0,reset,0,reset,reset,reset,reset
