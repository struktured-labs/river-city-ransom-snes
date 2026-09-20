; Shared production/diagnostic Memblers packet sender. A8/X16, DB=0.
; The receiver consumes port 1 as soon as port 0 matches its byte index.
spc_frame:
    lda #$7D
    jsr wait_port0
    bcs @return
.ifdef AUDIO_REUSE
    lda $1CC0
    beq @changed_packet
    ldy #0
@compare_packet:
    lda APU_PACKET,y
    cmp $1CC1,y
    bne @changed_packet
    iny
    cpy #$17
    bne @compare_packet
    lda #$D6
    sta $2140
    jsr wait_port0
    bcs @return
    ldy #$17
    clc
    rts
@changed_packet:
.endif
    lda #$D7
    sta $2140
    jsr wait_port0
    bcs @return
    ldy #0
.ifdef AUDIO_TRIPLE
@triple:
.ifdef AUDIO_TRANSFER_DELAY
    .repeat 32
        nop
    .endrepeat
.endif
    lda APU_PACKET,y
    sta $2141
    iny
    lda APU_PACKET,y
    sta $2142
    iny
    cpy #$17
    beq @triple_tail
    lda APU_PACKET,y
    sta $2143
    iny
    tya
    sec
    sbc #3
    bra @triple_publish
@triple_tail:
    stz $2143                 ; deterministic unused $4017 tail byte
    tya
    sec
    sbc #2
@triple_publish:
    sta $2140                 ; publish only after every data port is ready
    jsr wait_port0
    bcs @return
    cpy #$17
    bcc @triple
    clc
    rts
.else
.ifdef AUDIO_TOKEN_FIRST
    sty $2140                 ; deliberate old-order negative control
.endif
@byte:
.ifdef AUDIO_TRANSFER_DELAY
    .repeat 32                ; pause CPU before data, let receiver run
        nop
    .endrepeat
.endif
    lda APU_PACKET,y
.ifdef AUDIO_LENGTH_GATE
    cpy #$15
    bne :+
    APU_LENGTH_ENABLE
:
.endif
    sta $2141
.ifdef AUDIO_PAIR
    iny
    cpy #$17
    beq @single_tail
    lda APU_PACKET,y
    sta $2142
@single_tail:
    dey
.endif
    tya
.ifndef AUDIO_TOKEN_FIRST
    sta $2140                 ; publish token only AFTER its data is available
.endif
    jsr wait_port0
    bcs @return
    iny
.ifdef AUDIO_PAIR
    iny
    cpy #$17
    bcs @done
.else
    cpy #$17
    beq @done
.endif
.ifdef AUDIO_TOKEN_FIRST
    tya
    sta $2140
.endif
    bra @byte
@done:
.ifdef AUDIO_PAIR
    ldy #$17
.endif
.ifdef AUDIO_REUSE
    ldy #0
@remember_packet:
    lda APU_PACKET,y
    sta $1CC1,y
    iny
    cpy #$17
    bne @remember_packet
    lda #1
    sta $1CC0
    ldy #$17
.endif
    clc
.endif
@return:
    rts
