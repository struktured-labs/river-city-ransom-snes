; Same on-disk ring as audio_packet_log.asm; word copies and folded XOR.
; Still intrusive, diagnostic-only. Startup bytes are bound to the first build.
.setcpu "65816"
.a8
.i16
.segment "CODE"
.export log_frame, log_end
.incbin "logger.bin", 0, $80
log_frame:
    jsr spc_frame
    php
    rep #$20
    .a16
    pha
    phx
    phy
    sep #$20
    .a8
    phb
    bcc success
    lda #1
    bra status_ready
success:
    lda #0
status_ready:
    pha
    lda f:$20600E
    pha
    plb
    rep #$20
    .a16
    lda f:$20600C
    tax
    sep #$20
    .a8
    pla
    sta a:6,x
    lda #0
    sta a:31,x
    rep #$20
    .a16
    lda f:$206008
    sta a:0,x
    lda f:$20600A
    sta a:2,x
    lda f:$001C04
    sta a:4,x
    .repeat 11, I
        lda f:$000A00+2*I
        sta a:7+2*I,x
    .endrepeat
    sep #$20
    .a8
    lda f:$000A16
    sta a:29,x
    rep #$20
    .a16
    lda #0
    .repeat 15, I
        eor a:2*I,x
    .endrepeat
    pha
    xba
    sep #$20
    .a8
    eor 1,s                     ; fold saved low with high, no WRAM scratch
    sta a:30,x
    rep #$20
    .a16
    pla
    sep #$20
    .a8
    lda #$A5
    sta a:31,x
    rep #$20
    .a16
    txa
    clc
    adc #32
    cmp #$8000
    bne pointer_ready
    sep #$20
    .a8
    lda f:$20600E
    inc
    cmp #$30
    bne bank_ready
    lda #$20
bank_ready:
    sta f:$20600E
    lda f:$20600E
    cmp #$20
    beq first_bank
    rep #$20
    .a16
    lda #$6000
    bra pointer_ready
first_bank:
    rep #$20
    .a16
    lda #$6020
pointer_ready:
    sta f:$20600C
    lda f:$206008
    inc
    sta f:$206008
    bne total_ready
    lda f:$20600A
    inc
    sta f:$20600A
total_ready:
    sep #$20
    .a8
    plb
    rep #$20
    .a16
    ply
    plx
    pla
    plp
    .a8
log_end:
    rts
