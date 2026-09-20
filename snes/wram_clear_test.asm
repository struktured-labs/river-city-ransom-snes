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
    ; Poison every byte, including stack and highest address, before DMA.
    ldx #0
    lda #$A5
@poison:
    sta f:$7E0000,x
    sta f:$7F0000,x
    inx
    bne @poison
    clear_wram_dma
halt:
    bra halt               ; leave all WRAM untouched for the external oracle
interrupt:
    rti
.segment "HEADER"
    .byte "RCR WRAM CLEAR TEST  "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
