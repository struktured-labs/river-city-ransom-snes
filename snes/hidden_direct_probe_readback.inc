    sep #$20
    .a8
    lda #$80
    sta $2100
    sta $2115
    ldx #$2000
    stx $2116
    rep #$20
    .a16
    lda $2139
    ldx #0
@readback_vram:
    lda $2139
    sta f:$7E8000,x
    inx
    inx
    cpx #8192
    bne @readback_vram
