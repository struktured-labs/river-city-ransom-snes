; Interleaved logger retaining the original DB=0 poller and port accesses.
.setcpu "65816"
.a8
.i16
.segment "CODE"
.export log_frame, log_end
.incbin "logger.bin", 0, $80
.macro SRAM_ENTER
    phb
    lda f:$20600E
    pha
    plb
    rep #$20
    .a16
    lda f:$20600C
    tax
    sep #$20
    .a8
.endmacro
log_frame:
    lda #$7D
    jsr wait_port0
    bcc :+
    SRAM_ENTER
    jsr metadata
    jmp failed
:
    lda #$D7
    sta $2140
    SRAM_ENTER
    jsr metadata
    plb
    lda #$D7
    jsr wait_port0
    bcc :+
    SRAM_ENTER
    jmp failed
:
    .repeat 12, I
        lda $0A00+2*I
        sta $2141
        .if I < 11
            lda $0A01+2*I
            sta $2142
        .endif
        lda #2*I
        sta $2140
        SRAM_ENTER
        .if I < 11
            rep #$20
            .a16
            lda f:$000A00+2*I
            sta a:7+2*I,x
            sep #$20
            .a8
        .else
            lda f:$000A16
            sta a:29,x
            jsr record_check
        .endif
        plb
        lda #2*I
        jsr wait_port0
        bcc :+
        SRAM_ENTER
        jmp failed
:
    .endrepeat
    SRAM_ENTER
    clc
    bra finalize
failed:
    lda #1
    sta a:6,x
    jsr record_check
    sec
finalize:
    php
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
    plp
    plb
log_end:
    rts
metadata:
    lda #0
    sta a:31,x
    sta a:6,x
    rep #$20
    .a16
    lda f:$206008
    sta a:0,x
    lda f:$20600A
    sta a:2,x
    lda f:$001C04
    sta a:4,x
    sep #$20
    .a8
    rts
record_check:
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
    eor 1,s
    sta a:30,x
    rep #$20
    .a16
    pla
    sep #$20
    .a8
    rts
