.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.segment "WAIT"
    .incbin "wait.bin"
    jml BANK*$10000+after
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
    lda #1
    sta $420D
    lda #4
    sta $2133
    clear_wram_dma
    rep #$20
    .a16
    lda #$1234
    tcd
    sep #$30
    .a8
    .i8
    lda #$83
    pha
    plb
    sec
    xce
    ldx #STACK
    txs
    jml BANK*$10000+run
run:
:
    lda $213F
    lda $2137
    lda $213D
    cmp #<LINE
    bne :-
    lda $213D
    and #1
    cmp #>LINE
    bne :-
    ldx #$A6
    ldy #$59
    lda #$3C
    xba
    lda #FLAGS
    pha
    lda #$57
    plp
    jml WAIT_ENTRY
after:
    txa
    sta f:$7E6000
    tya
    sta f:$7E6001
    tdc
    sta f:$7E6002
    xba
    sta f:$7E6003
    phb
    pla
    sta f:$7E6004
    tsx
    txa
    sta f:$7E6005
    lda $213F
    lda $2137
    lda $213D
    sta f:$7E6006
    lda $213D
    and #1
    sta f:$7E6007
    lda #1
    sta a:$1C60
alive:
    lda $4212
    bmi alive
:
    lda $4212
    bpl :-
    inc a:$1C62
    bne alive
    inc a:$1C63
    bra alive
.segment "HEADER"
    .byte "RCR RETAINED WAIT    "
    .byte $31,$02,$0B,$00,$01,$33,$00
    .word 0,0
.segment "VECTORS"
    .word 0,0,0,0,0,0,0,0
    .word 0,0,0,0,0,0,reset,0
