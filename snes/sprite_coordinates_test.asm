.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.segment "CODE"
reset:
    jml SOURCE_BANK*$10000+entry
entry:
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
    lda #0
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
    lda #SOURCE_BANK-$40
    pha
    plb
    rep #$30
    .a16
    .i16
    ldx #$01FF
    txs
case_start:
    sep #$20
    .a8
    ldy #0
@poison:
    tya
    eor #$A5
    sta $0000,y
    iny
    cpy #256
    bne @poison
    ldx $0600
    .repeat 4,i
        lda f:$C90000+i,x
        sta $08+i
        lda f:$C90004+i,x
        sta $0E+i
    .endrepeat
    lda f:$C9000C,x
    sta $0612
    lda f:$C9000A,x
    sta $0610
    rep #$20
    .a16
    lda f:$C9000B,x
    and #$00FF
    tay
    lda f:$C90008,x
    sep #$20
    .a8
    sec
    xce
    .i8
    pha
    lda $0612
    pha
    plp
    pla
    ldx $0610
    jsr $EF11
    sta $0708
    php
    pla
    sta $070C
    stx $070A
    sty $070B
    xba
    sta $0709
    tsx
    stx $070D
    phb
    pla
    sta $070F
    clc
    xce
    rep #$30
    .a16
    .i16
    cld
    tsc
    xba
    sep #$20
    .a8
    sta $070E
    rep #$20
    .a16
    tdc
    sta $0710
    sep #$20
    .a8
    .repeat 4,i
        lda $08+i
        sta $0700+i
        lda $0E+i
        sta $0704+i
    .endrepeat
    stz $0712
    ldy #0
@guard:
    cpy #8
    bcc @check
    cpy #12
    bcc @next
    cpy #14
    bcc @check
    cpy #18
    bcc @next
@check:
    tya
    eor #$A5
    cmp $0000,y
    beq @next
    inc $0712
@next:
    iny
    cpy #256
    bne @guard
    ldx $0602
    .repeat 32,i
        lda $0700+i
        sta f:$7F0000+i,x
    .endrepeat
    rep #$20
    .a16
    lda $0600
    clc
    adc #16
    sta $0600
    lda $0602
    clc
    adc #32
    sta $0602
    inc $0604
    lda $0604
    cmp #CASES
    beq @done
    jmp case_start
@done:
    sep #$20
    .a8
    lda #1
    sta $1C60
@visible:
    lda $4212
    bmi @visible
@blank:
    lda $4212
    bpl @blank
    inc $1C62
    bne @visible
    inc $1C63
    bra @visible
.i8
.include "sprite_coordinates.inc"
interrupt:
    rti
.segment "ORIGINAL"
.ifdef OPTIMIZED
    jmp native_sprite_coordinates
    .res 18,$EA
.else
    ldx #0
@add:
    lda $08,x
    clc
    adc $0E,x
    sta $08,x
    lda $0F,x
    adc $09,x
    sta $09,x
    inx
    inx
    cpx #4
    bcc @add
.endif
.assert * = $EF26, lderror, "Original coordinate exit moved"
    rts
.segment "HEADER"
    .byte "RCR COORDINATE TEST  "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
