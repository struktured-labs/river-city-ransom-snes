.setcpu "65816"
.a8
.i16
.include "interrupt_policy.inc"
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
    lda #$80
    sta $1C20
    lda #1
.if SERVICED_EVENT
    lda #0                 ; early acknowledged NMI has no queued publication
.endif
    sta $1C79
    lda #2
    sta $1D00              ; ready row: late publisher must retain it
    lda #$0F
    sta $2100
    sep #$30
    .i8
    sec
    xce
    ldx #INITIAL_STACK
    txs
@blank:
    lda $4212
    bpl @blank
@visible:
    lda $4212
    bmi @visible
    lda $4210
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
    stz $4200
    lda #1
    sta $1C79
    .repeat DELAY_NOPS
        nop
    .endrepeat
    lda #1
    sta $1C0A
    ; Construct exactly the production P/PCL/PCH + A/X/Y return stack.
.if RETAINED_RETURN
    lda #>camera_deferred_nmi_return
    pha
    lda #<camera_deferred_nmi_return
.else
    lda #>ordinary_return
    pha
    lda #<ordinary_return
.endif
    pha
    lda #$40
    sec
    php
    pha
    lda #$56
    pha
    lda #$78
    pha
.ifdef CLEAR_FRESH
    lda $4210
.endif
    jmp nmi_rti_return
camera_deferred_nmi_return:
    bra returned
ordinary_return:
    bra returned
returned:
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
    lda $1C0A
    sta f:$7E6006
    ; Measure this VBlank only; do not count the next frame's event.
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
    stz $4200
    pha
    phx
    phy
    phd
.ifndef OMIT_ACK
    lda $4210
.endif
    inc $1C04
    inc $1C0A
    lda $1C0A
    cmp #1
    beq :+
    inc $6007
:
    clc
    xce
    rep #$30
    .a16
    .i16
    lda #$1E00
    tcd
    sep #$20
    .a8
    jsr native_video
    rep #$20
    .a16
    lda #0
    tcd
    sep #$30
    .a8
    .i8
    sec
    xce
    dec $1C0A
    lda $1C04
    cmp #3                 ; bound the missing-ack negative control
    bcs :+
    lda #$80
    sta $4200
:
    pld
    ply
    plx
    pla
    rti
interrupt:
    rti
nmi_rti_return:
.include "nmi_return_tail.inc"
.i16
.include "native_video.asm"
.segment "HEADER"
    .byte "RCR RETURN EDGE TEST "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,nmi,nmi,reset,interrupt
