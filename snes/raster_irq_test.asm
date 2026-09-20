.setcpu "65816"
.a16
.i16
.include "interrupt_policy.inc"
.segment "CODE"
reset:
    sei
    clc
    xce
    rep #$38
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
    ldx #$40
@clear:
    stz $1800,x
    dex
    bpl @clear
    lda #30
    sta $4209
    stz $420A
    jsr next_frame
.ifdef EXPERIMENTAL_RASTER
    stz $1C20
    lda #$20
    sta $1CA2
    load_interrupt_enable
.else
    lda #$20
.endif
    sta $4200
.ifdef DELAY_IRQ
@delay:
    lda $213F
    lda $2137
    lda $213D
    cmp #60
    bcc @delay
.endif
    rep #$20
    .a16
    lda #$1234
    tcd
    sep #$20
    .a8
    lda #$7E
    pha
    plb
    rep #$20
    .a16
    lda #$ABCD
    ldx #$5678
    ldy #$9ABC
.ifdef EMULATION
    sec
    xce
    .a8
    .i8
.endif
    sed
    sec
    cli
@wait:
    ; Long LDA would destroy the register sentinel: use WAI instead.
    wai
    php
    sei
.ifdef EMULATION
    clc
    xce
    rep #$30
    .a16
    .i16
.endif
    sta f:$7E1808
    stx $180A
    sty $180C
    sep #$20
    .a8
    pla
    sta $180E
    phb
    pla
    sta $180F
    rep #$20
    .a16
    tdc
    sta $1810
    tsx
    stx $1812
    lda #$600D
    sta $1814
    jmp halt

next_frame:
    lda $4212
    bpl next_frame
@active:
    lda $4212
    bmi @active
    rts

irq:
    php
.ifdef EMULATION
    clc
    xce
.endif
    rep #$30
    .a16
    .i16
    pha
    phx
    phy
    phd
    phb
    lda #0
    tcd
    sep #$20
    .a8
    pha
    plb
.ifndef OMIT_FIRST_ACK
    lda $4211
.else
    lda #$80
.endif
    sta $1801
    lda $4211
    sta $1802
    lda $213F
    lda $2137
    lda $213D
    sta $1803
    lda $213D
    and #1
    sta $1804
    inc $1800
.ifdef NESTED_NMI
    lda #1
    sta $1816
    lda $4210
    lda #$80
    sta $4200
    rep #$30
    .a16
    lda #$1E00
    tcd
    sep #$20
    .a8
    lda #$7E
    pha
    plb
    rep #$30
    .a16
    lda #$CAFE
    ldx #$1357
    ldy #$2468
    sed
    sec
    wai
    php
    sta $1820
    stx $1822
    sty $1824
    sep #$20
    .a8
    pla
    sta $1826
    phb
    pla
    sta $1827
    rep #$20
    .a16
    tdc
    sta $1828
    lda #0
    tcd
    sep #$20
    .a8
    pha
    plb
    stz $1816
.endif
    stz $4200
    plb
    pld
    rep #$30
    .a16
    ply
    plx
.ifdef CLOBBER_X
    ldx #0
.endif
    pla
.ifdef EMULATION
    sec
    xce
.endif
    plp
    rti
nmi:
    php
    rep #$30
    .a16
    pha
    phx
    phy
    phd
    phb
    lda #0
    tcd
    sep #$20
    .a8
    pha
    plb
    lda $4210
    inc $1817
    lda $1816
    sta $1818
    lda $213F
    lda $2137
    lda $213D
    sta $1819
    lda $213D
    and #1
    sta $181A
    plb
    pld
    rep #$30
    .a16
    ply
    plx
.ifdef NMI_CLOBBER_X
    ldx #0
.endif
    pla
    plp
    rti
halt:
    bra halt
.segment "HEADER"
    .byte "RCR RASTER IRQ TEST  "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,halt,halt,halt,nmi,0,irq
    .word 0,0,halt,0,halt,nmi,reset,irq
