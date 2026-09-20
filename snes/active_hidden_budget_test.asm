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
    lda #$80
    sta $2100
    clear_wram_dma
    ldx #$1FFF
    txs
    rep #$20
    .a16
    lda #$1E00
    tcd
    sep #$20
    .a8
next_case:
    lda a:$0600
    sta a:$1CE1
    lda a:$0601
    sta a:$1CA0
    ldx #$1357
    ldy #$2468
    jsr $885D
    cpx #$1357
    bne failed
    cpy #$2468
    bne failed
    lda a:$0601
    cmp #2
    bne ordinary
    lda a:$0600
    beq idle_budget
    lda #15
    bra compare
idle_budget:
    lda #16
    bra compare
ordinary:
    lda #2
compare:
    cmp a:$1C6B
    bne failed
    rep #$20
    .a16
    tdc
    cmp #$1E00
    bne failed
    tsc
    cmp #$1FFF
    bne failed
    sep #$20
    .a8
    inc a:$0600
    bne next_case
    inc a:$0601
    lda a:$0601
    cmp #4
    bne next_case
    lda #1
    sta a:$1C60
    bra idle
failed:
    sep #$20
    .a8
    lda #$FF
    sta a:$1C60
idle:
    lda a:$4212
    bmi idle
blank:
    lda a:$4212
    bpl blank
    inc a:$1C62
    bne idle
    inc a:$1C63
    bra idle
interrupt:
    rti
.segment "GATE"
    .incbin "gate.bin"
    rts
.segment "HELPER"
    .incbin "helper.bin"
.segment "HEADER"
    .byte "RCR ACTIVE ROW TEST  "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
