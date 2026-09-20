; Real hardware-register/NMI fixture for the extracted camera completion hook.
.setcpu "65816"
.a8
.i8
.include "interrupt_policy.inc"
.include "wram_clear.inc"
.segment "CODE"
reset:
    sei
    clc
    xce
    rep #$38
    .a16
    .i16
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
    sta $2133              ; RCR uses 239 visible lines, NMI at line 240
    lda #$80
    sta $1C20
    lda #1
    sta $1CEB
    sta $1CE1
    lda #$10
    sta $3B
    lda #1
    sta $3D
.ifdef STATIC_ARM_TEST
    stz $1CEB
    lda #$30
    sta $1C94
    sta $1C97
    lda #1
    sta $1C95
    sta $1C98
    lda #STATIC_TASK
    sta $0100
    lda #STATIC_GUARD
    sta $0107
    lda #STATIC_PAUSE
    sta $3F
    lda #STATIC_FADE
    sta $3E
    lda #STATIC_LEVEL
    sta $0692
    lda #STATIC_TRANSITION
    sta $1CA0
.endif
    sep #$30
    .a8
    .i8
    sec
    xce
@wait_blank:
    lda $4212
    bpl @wait_blank
@wait_visible:
    lda $4212
    bmi @wait_visible
    lda $4210              ; discard only the previous frame's event
.if SERVICED_EVENT
    lda #$80
    sta $4200
.endif
@target:
    lda $213F
    lda $2137
    lda $213D
    cmp #TARGET_LINE
    bne @target
    .repeat DELAY_NOPS
        nop
    .endrepeat
    lda #$40
    ldx #$56
    ldy #$78
    sec
    jsr camera_deferred_nmi_exit
    sta f:$7E6000
    php
    pla
    sta f:$7E6001
    txa
    sta f:$7E6002
    tya
    sta f:$7E6003
    tsx
    txa
    sta f:$7E6004
    ; If the old wait already wrapped to line zero, do not accidentally wait
    ; for the NEXT VBlank and count that as service of the dropped event.
    lda $213F
    lda $2137
    lda $213D
    cmp #200
    bcc @measure
@finish_blank:
    lda $4212
    bpl @finish_blank
@finish_visible:
    lda $4212
    bmi @finish_visible
@measure:
    stz $4200
    lda $1C04
    sta f:$7E6005
    lda #1
    sta $1C60
@alive_visible:
    lda $4212
    bmi @alive_visible
@alive_blank:
    lda $4212
    bpl @alive_blank
    inc $1C62
    bne @alive_visible
    inc $1C63
    bra @alive_visible
nmi:
    pha
.ifndef OMIT_ACK
    lda $4210
.endif
    inc $1C04
    pla
    rti
interrupt:
    rti
.include "camera_hook.inc"
.segment "HEADER"
    .byte "RCR CAMERA EDGE TEST"
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,nmi,nmi,reset,interrupt
