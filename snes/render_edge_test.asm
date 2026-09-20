.setcpu "65816"
.macpack longbranch
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
    ldx #$01FF
    txs
    rep #$20
    .a16
    lda #$1B00
    tcd
    sep #$20
    .a8
    lda #DATA_BANK
    pha
    plb
    sec
    xce
    .i8
next_case:
    stz a:$0601
    stz a:$1CA0
    lda a:$0600
    and #3
    tax
    lda f:SOURCE_BANK*$10000+values,x
    sta a:$1C0A
    lda a:$0600
    lsr
    lsr
    and #3
    tax
    lda f:SOURCE_BANK*$10000+values,x
    sta a:$1C79
    lda a:$0600
    lsr
    lsr
    lsr
    lsr
    tax
    lda f:SOURCE_BANK*$10000+values,x
    sta a:$1C20
    lda #$A5
    xba
    ldx #$5A
    ldy #$C3
    lda #FLAGS
    pha
    plp
    lda #2
    php
    pla
    sta a:$0612
    lda #2
    jsr $7F80
    sta a:$0610
    php
    pla
    sta a:$0611
    stx a:$0613
    sty a:$0614
    xba
    sta a:$0615
    tsx
    stx a:$0616
    cld
    lda a:$0610
    cmp #2
    jne failed
    lda a:$0611
    cmp a:$0612
    jne failed
    lda a:$0613
    cmp #$5A
    jne failed
    lda a:$0614
    cmp #$C3
    jne failed
    lda a:$0615
    cmp #$A5
    jne failed
    lda a:$0616
    cmp #$FF
    jne failed
    lda a:$1CA0
    cmp #2
    jne failed
    tdc
    cmp #0
    jne failed
    xba
    cmp #$1B
    jne failed
    phb
    pla
    cmp #DATA_BANK
    jne failed
    lda a:$1C0A
    bne no_call
    lda a:$1C79
    beq no_call
    lda a:$1C20
    bpl no_call
    lda #PASSES
    bra compare_calls
no_call:
    lda #0
compare_calls:
    cmp a:$0601
    jne failed
    inc a:$0600
    lda a:$0600
    cmp #64
    jne next_case
    lda #1
    sta a:$1C60
    bra idle
failed:
    lda #$FF
    sta a:$1C60
idle:
    lda a:$4212
    bmi idle
blank:
    lda a:$4212
    bpl blank
    inc a:$1C62
    bne idle
    inc a:$1C63
    bra idle
values:
    .byte 0,1,$80,$FF
interrupt:
    rti
.segment "BRIDGE"
    ; Stand-in for the separately tested native bridge: deliberately changes
    ; low A and flags. This fixture tests dispatch/outer preservation, not VRAM.
    inc a:$0601
    lda #$55
    rtl
.segment "HELPER"
    .incbin "edge.bin"
.segment "HEADER"
    .byte "RCR EDGE HELPER TEST "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
