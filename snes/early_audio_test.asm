; Production early bridge + real bank-switch helper; synthetic sound/packet
; endpoints isolate scheduling ABI. Real game packet checks are separate.
.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.include "early_audio_abi.inc"
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
    sta $1C0A
    lda #$C3
    sta $1C02
    sta $1C03
    lda #6
    sta $FB
    lda #4
    sta $FC
    sta $1C16
    lda #5
    sta $FD
    sta $1C17
    lda #$34
    sta $1C04
    lda #$12
    sta $1C05
    rep #$20
    .a16
    lda #$1234
    tcd
    sep #$30
    .a8
    .i8
    sec
    xce
    jml $C30000+caller
caller:
    lda #$83
    pha
    plb
    lda #$34
    ldx #$56
    ldy #$78
    sec
    jsl $C10000+EARLY_AUDIO_ENTRY
    sta f:$7E6000
    php
    pla
    sta f:$7E6001
    txa
    sta f:$7E6002
    tya
    sta f:$7E6003
    phb
    pla
    sta f:$7E6004
    phd
    pla
    sta f:$7E6005
    pla
    sta f:$7E6006
    phk
    pla
    sta f:$7E6007
    tsx
    txa
    sta f:$7E6008
    lda a:EARLY_AUDIO_VALID
    sta f:$7E6009
    lda a:EARLY_AUDIO_NMI_LO
    sta f:$7E600A
    lda a:EARLY_AUDIO_NMI_HI
    sta f:$7E600B
    ldy #0
@cases:
    lda cases,y
    sta a:$1C04
    iny
    lda cases,y
    sta a:$1C05
    iny
    lda cases,y
    sta a:EARLY_AUDIO_NMI_LO
    iny
    lda cases,y
    sta a:EARLY_AUDIO_NMI_HI
    iny
    lda cases,y
    sta a:EARLY_AUDIO_VALID
    iny
    stz a:$1CF5
    jsr classify
    lda a:$1CF5
    cmp cases,y
    bne fail
    lda a:EARLY_AUDIO_VALID
    bne fail
    iny
    inc a:$1C72
    cpy #cases_end-cases
    bne @cases
    lda #1
    sta a:$1C60
    bra alive
fail:
    lda #1
    sta a:$1C61
    lda #$EE
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
classify:
    consume_early_audio already
    rts
already:
    inc a:$1CF5
    rts
cases:
    .include "early_audio_cases.inc"
cases_end:
interrupt:
    rti
.segment "DRIVER"
    ; Cross into a different mapped program/data bank through the real helper.
    lda #5
    jsr bank_switch_enter
    inc a:$1CF2
    lda #$98
    ldx #$BA
    ldy #$DC
    rts
.segment "RESTORE"
    ; Restore paired-bank state, retaining the saved mapper selection.
    lda $FB
    sta a:$1CF6
    lda $FC
    lsr
    jsr bank_switch_enter
    lda a:$1CF6
    sta $FB
    sta a:$1C19
    inc a:$1CF3
    rts
.segment "HEADER"
    .byte "RCR EARLY AUDIO TEST"
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
