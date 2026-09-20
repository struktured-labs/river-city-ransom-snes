; Asset-free, deterministic hardware audio experiment. Native A8/X16, DB=0.
; Stream in D3: one byte packet count followed by zero/one 23-byte packet.
; Frame count in mirrored WRAM $1800, packet count $1802, complete $1804.
; Sixteen binary frame bits and their inverse make video identity observable.
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
    ; Clear VRAM, then create a solid colour-1 tile (tile one).
    lda #$80
    sta $2115
    stz $2116
    stz $2117
    rep #$20
    .a16
    lda #0
    ldx #$8000
@clear_vram:
    sta $2118
    dex
    bne @clear_vram
    lda #8
    sta $2116
    lda #$00FF
    ldx #8
@tile:
    sta $2118
    dex
    bne @tile
    sep #$20
    .a8
    stz $2121
    stz $2122
    stz $2122
    lda #$FF
    sta $2122
    lda #$7F
    sta $2122
    stz $2105
    lda #$10
    sta $2107
    stz $210B
    stz $210D
    stz $210D
    stz $210E
    stz $210E
    stz $2123
    stz $2124
    stz $2125
    stz $212E
    stz $212F
    stz $2130
    stz $2131
    stz $2133
    lda #1
    sta $212C
    stz $212D
    lda #$0F
    sta $2100
    jsr spc_upload
    bcs fail
    lda #1
    sta $1C60
main:
    jsr wait_frame
.ifdef DOUBLE_FRAME_WAIT
    jsr wait_frame
.endif
    rep #$20
    .a16
    lda $1800
    cmp #SOURCE_FRAMES
    sep #$20
    .a8
    bcs finished
    ; Draw before the potentially long SPC handshake. VRAM writes after the
    ; sender can land outside VBlank and leave a torn frame-code on hardware.
    rep #$20
    .a16
    inc $1800
    sep #$20
    .a8
    jsr show_frame
    jsr next_byte
    cmp #0
    beq @empty
    cmp #1
    bne fail
    ldy #0
@copy:
    jsr next_byte
    sta APU_PACKET,y
    iny
    cpy #23
    bne @copy
    jsr spc_frame
    bcs fail
    rep #$20
    .a16
    inc $1802
    sep #$20
    .a8
@empty:
    bra main
finished:
    lda #1
    sta $1804
    bra main
fail:
    inc $1C0B
    lda #$EE
    sta $1C60
@failed:
    bra @failed
next_byte:
    ldx $1806
    lda f:$D30000,x
    inx
    stx $1806
    rts
wait_frame:
    lda $4212
    bmi wait_frame
@blank:
    lda $4212
    bpl @blank
    inc $1C62
    bne :+
    inc $1C63
:
    rts
show_frame:
    rep #$20
    .a16
    lda #$1088
    sta $2116
    lda $1800
    sta $1808
    ldx #16
@bit:
    lsr $1808
    lda #0
    rol
    sta $2118
    dex
    bne @bit
    lda #$10A8
    sta $2116
    lda $1800
    eor #$FFFF
    sta $1808
    ldx #16
@inverse:
    lsr $1808
    lda #0
    rol
    sta $2118
    dex
    bne @inverse
    sep #$20
    .a8
    rts
.include "native_audio.asm"
irq:
    rti
.segment "HEADER"
.byte "RCR PACKET REPLAY    "
.byte $21,$00,$0B,$00,$01,$00,$00
.word $FFFF,0
.segment "VECTORS"
.word 0,0,irq,irq,irq,irq,0,irq
.word 0,0,irq,0,irq,irq,reset,irq
