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
    .include "setup.inc"
    rep #$20
    .a16
    lda #$1234
    tcd
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
    lda $4210
    lda #$80
    sta $4200
    ldx #$56
    ldy #$78
    lda #$5A
    xba
    lda #INPUT_FLAGS
    pha
    plp
    lda #$42
    jsr gameplay_phase_start
    sta f:$7E6000
    php
    pla
    sta f:$7E6004
    txa
    sta f:$7E6002
    tya
    sta f:$7E6003
    xba
    sta f:$7E6001
    tsx
    txa
    sta f:$7E6005
    phd
    pla
    sta f:$7E6006
    pla
    sta f:$7E6007
    phb
    pla
    sta f:$7E6008
    lda $213F
    lda $2137
    lda $213D
    sta f:$7E600A
    lda $213D
    and #1
    sta f:$7E600B
wait_nmi:
    lda a:$1BA1
    beq wait_nmi
    stz $4200
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
gameplay_iteration_start:
    lda #1
    sta a:$1CE1
    lda #0
    sta a:$010B
    rts
nmi:
    pha
    lda $4210
    inc a:$1BA1
    pla
    rti
irq:
    rti
.include "main_phase.inc"
.segment "HEADER"
    .byte "RCR MAIN PHASE TEST  "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,irq,irq,irq,nmi,0,irq
    .word 0,0,irq,0,irq,nmi,reset,irq
