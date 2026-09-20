; A16/X16, DB=0, D=1E00. Preserve row X and scan budget Y.
; Both planes together use exactly $1E bytes (one/two rows = 64/128).
publish_planar_row:
    .a16
    txa
    .repeat 5
        asl
    .endrepeat
    sta $08
    clc
    adc #$2000
    sta $2116
    lda $08
    clc
    adc #$3000
    sta $4302
    lda $1E
    lsr
    sta $0C
    sta $4305
    sep #$20
    .a8
    stz $4300              ; single B-bus port, increment source
    stz $2115              ; increment VRAM address after low-byte write
    lda #$18
    sta $4301
    lda #$7E
    sta $4304
    lda #1
    sta $420B
    rep #$20
    .a16
    lda $08
    clc
    adc #$2000
    sta $2116              ; high plane must restart at the same VRAM word
    lda $08
    clc
    adc #$4000
    sta $4302
    lda $0C
    sta $4305
    sep #$20
    .a8
    lda #$80
    sta $2115              ; increment after high-byte write
    lda #$19
    sta $4301
    lda #1
    sta $420B
    ; Restore the ordinary publisher's channel/VMAIN convention.
    lda #1
    sta $4300
    lda #$18
    sta $4301
    rep #$20
    .a16
    rts
