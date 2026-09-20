; Multiple real production rows, repeated producer calls, and actual VRAM.
.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.segment "CODE"
reset:
    jml $C00000+fast_entry
fast_entry:
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
    lda #1
    sta $420D
    lda #$80
    sta $2100
    clear_wram_dma
    ldx #0
@staging:
    rep #$20
    .a16
    stx $00
    txa
    xba
    eor $00
    sep #$20
    .a8
    sta f:$7E3000,x
    inx
    cpx #8192
    bne @staging
    rep #$20
    .a16
    lda #$1E00
    tcd
    .include "hidden_direct_probe_setup.inc"
    .repeat CALLS, call
        sep #$20
        .a8
        ldx #0
:
        lda f:$C00000+shadow_data+call*4096,x
        sta f:$7F2000,x
        inx
        cpx #4096
        bne :-
        ldx #0
:
        lda f:$C00000+flags_data,x
        sta $1D00,x
        lda #2
        sta $1E80,x
        inx
        cpx #128
        bne :-
        lda #MIRROR_MODE
        sta $1C18
        lda #PATTERN_HALF ^ (call*16)
        sta $1C20
        sta $1C78
        lda #1
        sta $1C79
        sta $1C85
        lda #SOURCE_ROW
        sta $1C76
        lda #$C0
        sta $0100
        rep #$20
        .a16
        jsr native_prepare
    .endrepeat
cache_test_return:
    .include "hidden_direct_probe_readback.inc"
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
interrupt:
    rti
.include "native_prepare.asm"
shadow_data:
    .incbin "shadow.bin"
flags_data:
    .incbin "flags.bin"
.segment "HEADER"
    .byte "RCR HIGH CACHE TEST "
    .byte " "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
