    ; Poison the actual tilemap VRAM, not just the staging snapshot.
    sep #$20
    .a8
    lda #$80
    sta $2115
    ldx #$2000
    stx $2116
    rep #$20
    .a16
    lda #$A55A
    ldx #4096
@poison_vram:
    sta $2118
    dex
    bne @poison_vram
    sep #$20
    .a8
    ldx #0
    lda #2
@requirements:
    sta $1E80,x
    inx
    cpx #128
    bne @requirements
    lda #TRANSITION_STATE
    sta $1CA0
    lda #$0F
    sta $2100              ; test must prove the helper forces blank itself
@active_display:
    lda $4212
    bmi @active_display
    rep #$20
    .a16
