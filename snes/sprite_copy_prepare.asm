; Enter after translated NES OAM copy: E=0, A16/I16, NMI masked.
; Replay the displaced dirty latch, then update only the sprite producer.
; Preserve the adapter's A/X/Y/D/DB/P (including the high accumulator byte).
.setcpu "65816"
.a16
.i16
.segment "CODE"
.export sprite_copy_prepare
sprite_copy_prepare:
    sep #$20
    .a8
    lda #1
    sta a:$1C87
    rep #$20
    .a16
    php
    pha
    phx
    phy
    phd
    phb
    lda #$1E00
    tcd
    sep #$20
    .a8
    lda #0
    pha
    plb
    ; Initialization/hidden transitions retain their original full producer.
    lda a:$1C79
    beq done
    lda a:$1CA0
    bne done
    jsr SPRITE_DELTA
done:
    rep #$30
    .a16
    .i16
    plb
    pld
    ply
    plx
    pla
    plp
    rtl
