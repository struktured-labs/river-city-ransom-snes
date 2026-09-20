; Diagnostic only: log gated packets AFTER their bounded SPC transfer.
; Adds CPU work. Never describe captures using this as timing-neutral.
.setcpu "65816"
.a8
.i16
.segment "CODE"
.export log_upload, log_frame

log_upload:
    jsr spc_upload
    php
    rep #$20
    .a16
    pha
    sep #$20
    .a8
    ; Reset the header every boot. Old ring contents are outside total=0.
    .repeat 8, I
        lda magic+I
        sta f:$206000+I
    .endrepeat
    lda #0
    .repeat 8, I
        sta f:$206008+I
    .endrepeat
    lda #$20
    sta f:$20600C
    sta f:$20600E
    lda #$60
    sta f:$20600D
    rep #$20
    .a16
    pla
    plp
    .a8
    rts
magic: .byte "RCRLOG01"

log_frame:
    jsr spc_frame
    php
    rep #$20
    .a16
    pha                         ; also preserve hidden B accumulator
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
    sta a:6,x                   ; transfer timeout flag, not receiver proof
    lda #0
    sta a:31,x                  ; invalidate slot before changing contents
    .repeat 4, I
        lda f:$206008+I
        sta a:I,x
    .endrepeat
    lda f:$001C04
    sta a:4,x
    lda f:$001C05
    sta a:5,x
    .repeat 23, I
        lda f:$000A00+I
        sta a:7+I,x
    .endrepeat
    lda #0
    .repeat 30, I
        eor a:I,x
    .endrepeat
    sta a:30,x                  ; XOR is a corruption check, not a CRC
    lda #$A5
    sta a:31,x                  ; commit slot last
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
    ; bank 20 reserves its first slot for the header.
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
    rts
