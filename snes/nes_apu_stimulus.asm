; Asset-free NROM/UxROM player for captured APU writes. One source frame per VBlank.
; Within-frame SNES beam timing is deliberately NOT claimed cycle-equivalent.
.setcpu "6502"
.ifndef BANKED
BANKED = 0
.endif
.segment "HEADER"
.if BANKED
.byte $4E,$45,$53,$1A,8,1,$20,0,0,0,0,0,0,0,0,0
stimulus = $8000
.else
.byte $4E,$45,$53,$1A,2,1,0,0,0,0,0,0,0,0,0,0
.endif
.segment "CODE"
reset:
    sei
    cld
    ldx #$FF
    txs
    lda #0
    sta $2000
    sta $2001
    sta $4010
    sta $4015
    ldx #0
@clear:
    sta $0200,x
    inx
    bne @clear
    lda #$40
    sta $4017
    bit $2002
    jsr vblank
    jsr vblank
.if BANKED
    lda #0
    sta $03
    sta bank_select
.endif
    lda #<stimulus
    sta $00
    lda #>stimulus
    sta $01
    lda #1
    sta $0203
frame:
    jsr vblank
    jsr next_byte
    sta $02
empty_count_check:
    cmp #0               ; next_byte's pointer increment changes Z
    beq complete_frame
write_next:
    jsr next_byte
    tax
    jsr next_byte
apu_store:
    sta $4000,x
    sta $0220,x
    inc $0204
    bne :+
    inc $0205
:
    dec $02
    bne write_next
complete_frame:
    lda $4015
    sta $0206
    inc $0200
    bne :+
    inc $0201
:
    lda $0200
    cmp #<SOURCE_FRAMES
    bne frame
    lda $0201
    cmp #>SOURCE_FRAMES
    bne frame
    lda #1
    sta $0202
@done:
    jmp @done
next_byte:
    ldy #0
    lda ($00),y
    inc $00
    bne next_byte_done
    inc $01
.if BANKED
    pha
    lda $01
    cmp #$C0
    bne next_byte_restore
    lda #$80
    sta $01
    inc $03
    txa
    pha
    ldx $03
    txa
bank_store:
    sta bank_select,x     ; table data equals bank, safe with bus conflicts
    pla
    tax
next_byte_restore:
    pla
.endif
next_byte_done:
    rts
vblank:
    bit $2002
    bpl vblank
    rts
irq:
    rti
.if BANKED
.segment "SELECT"
bank_select:
.byte 0,1,2,3,4,5,6,7
.else
stimulus:
    .incbin "stimulus.bin"
.endif
.segment "VECTORS"
.word irq,reset,irq
.segment "CHR"
.res 8192,0
