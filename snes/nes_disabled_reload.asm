; Original-platform, asset-free ordered APU write diagnostic (NROM).
.setcpu "6502"
.ifdef NES_PULSE2
PULSE_BASE = $4004
PULSE_ENABLE = 2
.else
PULSE_BASE = $4000
PULSE_ENABLE = 1
.endif
.segment "HEADER"
.byte $4E,$45,$53,$1A,2,1,0,0,0,0,0,0,0,0,0,0
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
    sta $0200
    sta $0201
    sta $0202
    sta $0203
.ifdef NES_RETRIGGER
    sta $0205
.endif
    lda #$40
    sta $4017
    bit $2002
    jsr vblank
    jsr vblank
    lda #PULSE_ENABLE
    sta $4015
.ifdef NES_RETRIGGER
    lda #$3F
.else
    lda #$BF
.endif
    sta PULSE_BASE
    lda #8
    sta PULSE_BASE+1
    lda #$FD
    sta PULSE_BASE+2
    lda #0
    sta PULSE_BASE+3
    lda #1
    sta $0203
frame:
    jsr vblank
    inc $0200
    bne :+
    inc $0201
:
    lda $0201
    bne status
    lda $0200
    cmp #120
    beq disable_reload
    cmp #180
    beq restart
    cmp #240
    bne status
    lda #$7E
    sta PULSE_BASE+2
    lda #0
    sta PULSE_BASE+3
    lda #3
    sta $0202
    jmp status
disable_reload:
    lda #0
    sta $4015
.ifndef NES_RETRIGGER
    sta PULSE_BASE+3      ; phase reset, but length load is disabled
    lda #PULSE_ENABLE
    sta $4015             ; re-enable alone cannot restore length
.else
    lda #1
.endif
    sta $0202
    jmp status
restart:
.ifdef NES_RETRIGGER
    lda #PULSE_ENABLE
    sta $4015
.endif
    lda #0
    sta PULSE_BASE+3      ; valid reload now that channel is enabled
    lda #2
    sta $0202
status:
.ifdef NES_RETRIGGER
    lda $0200
    and #31
    bne :+
    lda #0
.ifdef NES_NO_RETRIGGER
    sta $0206             ; same-cycle control: no APU high-timer write
.else
    sta PULSE_BASE+3
.endif
    inc $0205
:
.endif
    lda $4015
    and #PULSE_ENABLE
    sta $0204
    jmp frame
vblank:
    bit $2002
    bpl vblank
    rts
irq:
    rti
.segment "VECTORS"
.word irq,reset,irq
.segment "CHR"
.res 8192,0
