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
    sta a:$1B80
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
    .repeat DELAY_NOPS
        nop
    .endrepeat
    ldx #$56
    ldy #$78
.if GUARDED
    jsr second_tick_prepare_camera
.else
    jsr second_tick_prepare_service
.endif
    ; The bridge burns cycles without touching the latched beam counters.
    lda $213D
    sta f:$7E6006
    lda $213D
    and #1
    sta f:$7E6007
    lda a:$1B80
    sta f:$7E6008
    lda a:$1BA0
    sta f:$7E6009
    lda $213F
    lda $2137
    lda $213D
    sta f:$7E600A
    lda $213D
    and #1
    sta f:$7E600B
    lda #$80
    sta $4200
next_sixty:
    lda $213F
    lda $2137
    lda $213D
    cmp #60
    bne next_sixty
    lda $213D
    and #1
    bne next_sixty
    stz $4200
    txa
    sta f:$7E6000
    tya
    sta f:$7E6001
    phd
    pla
    sta f:$7E6002
    pla
    sta f:$7E6003
    phb
    pla
    sta f:$7E6004
    tsx
    txa
    sta f:$7E6005
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
video_prepare_bridge:
    inc a:$1BA0
    phx
    phy
    ldy #6
outer:
    ldx #255
inner:
    dex
    bne inner
    dey
    bne outer
    ply
    plx
    rtl
nmi:
    pha
    lda $4210
    lda $213F
    lda $2137
    lda $213D
    sta f:$7E600C
    lda $213D
    and #1
    sta f:$7E600D
    inc a:$1BA1
    jsr second_tick_prepare_fallback
    pla
    rti
irq:
    rti
.include "second_tick_prepare.inc"
.include "second_tick_deadline.inc"
.segment "HEADER"
    .byte "RCR PREPARE DEADLINE "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,irq,irq,irq,nmi,0,irq
    .word 0,0,irq,0,irq,nmi,reset,irq
