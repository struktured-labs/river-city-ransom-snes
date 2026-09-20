; Execute a complete production write stub, including its real RTS or
; coroutine JMP tail and actual SNES NMI enable/wait behavior.
.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.segment "CODE"
.export run, after, nmi
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
    ldx #$02FF
poison:
    lda #$5A
    sta a:$1B00,x
    dex
    bpl poison
    lda #OLD_CTRL
    sta a:$1C20
    lda #LATCH
    sta a:$1C25
    lda #$20
    sta a:$1C27
    lda #$1F
    sta a:$1C26
    lda #0
    sta a:$1C18
    sta a:$1C06
    sta a:$1C60
    sta a:$1C61
    sta a:$1C62
    sta a:$1C63
    sta a:$1C6A
    lda #DEPTH
    sta a:$1C0A
    lda #PAIR
    sta a:$1C83
    lda #TASK
    sta a:$0100
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
wait_line:
    lda $213F
    lda $2137
    lda $213D
    cmp #WAITLINE
    bne wait_line
    lda $213D
    and #1
    bne wait_line
    ldx #INPUT_X
    ldy #INPUT_Y
    lda #FLAGS
    pha
    lda #INPUT_A
    plp
    jml BANK*$10000+run
run:
.if RESUME
    jmp STUB
.else
    jsr STUB
.endif
after:
    sta f:$7E6000
    php
    pla
    sta f:$7E6002
    xba
    sta f:$7E6001
    xba
    txa
    sta f:$7E6003
    tya
    sta f:$7E6004
    tdc
    sta f:$7E6005
    xba
    sta f:$7E6006
    xba
    phb
    pla
    sta f:$7E6007
    tsx
    txa
    sta f:$7E6008
    lda a:$1C6A
    sta f:$7E600A
    lda $4212
    and #$80
    sta f:$7E600B
    cld
    lda #1
    sta a:$1C60
alive:
    lda $4212
    bmi alive
blank:
    lda $4212
    bpl blank
    inc a:$1C62
    bne alive
    inc a:$1C63
    bra alive
nmi:
    pha
    lda $4210
    inc a:$1C6A
    pla
    ; E=1 RTI does not restore PB. NMI is enabled only after the private
    ; callee returned to the caller bank. Resume through that bank's RTI.
    jml BANK*$10000+return_irq
return_irq:
    rti
.if RESUME
.segment "RETURN"
    jmp after
.endif
.segment "HEADER"
    .byte "RCR FULL PPU STUB    "
    .byte $31,$00,$0B,$00,$01,$00,$00
    .word $FFFF,$0000
.segment "VECTORS"
    .word 0,0,reset,reset,reset,reset,reset,reset
    .word 0,0,return_irq,0,return_irq,nmi,reset,return_irq
