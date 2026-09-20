.setcpu "65816"
.include "wram_clear.inc"
.a8
.i16
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
    lda #1
    sta $420D
    sep #$30
    .i8
    sec
    xce
    jml $C70000+caller
caller:
    lda #$87
    pha
    plb
    ldx #0
@seed:
    txa
    eor #SEED
    sta a:$0110,x
    eor #$A5
    sta f:$7F3F00,x
    sta a:$1D00,x
    inx
    bne @seed
    lda #CTRL
    sta a:$1C20
    lda #<ADDRESS
    sta a:$1C26
    lda #>ADDRESS
    sta a:$1C27
    lda #DEPTH
    sta a:$1C0A
    lda #BANK_GUARD
    sta a:$1C83
    lda #COUNT
    sta a:$1C09
    lda #$12
    xba
    lda #$34
    tcd
    lda #FLAGS
    pha
    plp
    ldx #START_X
    ldy #$56
    jmp $E477
after_copy:
    sta f:$7E6000
    php
    pla
    sta f:$7E6001
    xba
    sta f:$7E6002
    txa
    sta f:$7E6003
    tya
    sta f:$7E6004
    phb
    pla
    sta f:$7E6005
    phd
    pla
    sta f:$7E6006
    pla
    sta f:$7E6007
    tsx
    txa
    sta f:$7E6008
    phk
    pla
    sta f:$7E6009
    lda #1
    sta a:$1C60
alive:
    lda $4212
    bmi alive
@blank:
    lda $4212
    bpl @blank
    inc a:$1C62
    bne alive
    inc a:$1C63
    bra alive
interrupt:
    rti
.segment "COPY"
copy:
.if FAST
    jmp palette_copy_loop
.else
    lda a:$0110,x
.endif
    jsr io_write_stub
    inx
    cpx #32
    bcc copy
    jmp after_copy
.segment "HEADER"
    .byte "RCR PALETTE COPY TEST"
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
