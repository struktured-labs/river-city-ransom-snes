; Native A8/X16, DB=0, called only inside the checked NMI final batch.
; Preview a completed original palette without changing original RAM,
; PPU shadow, source cache, write counters or the original dirty flag.
.setcpu "65816"
.a8
.i16
.segment "CODE"
pending_palette:
    .assert pending_palette = $7000, lderror, "Pending palette ABI moved"
    php
    pha
    phx
    phy
    lda a:$1C79
    beq @return
    lda a:$1C0A
    cmp #1
    bne @return
    lda a:$1C83
    bne @return
    lda a:$0100
    and #$C0
    cmp #$C0
    bne @return
    lda a:$0107
    bmi @return
    lda a:$003E
    and #$0A
    cmp #$0A
    bne @return
    ; C50B precedes E461. Read commands can write arbitrary zero-page state.
.ifdef EXPERIMENTAL_PENDING_PALETTE_WRITE_HEAD
    jsr pending_palette_write_head
    bcc @return
.else
    lda a:$06B6
    cmp a:$06B7
    bne @return
.endif
    lda a:$1CE0
    bne @return
    lda a:$1CA0
    bne @convert
    lda a:$1CEB
    beq @convert
    lda a:$1CE1
    beq @convert
@return:
    ply
    plx
    pla
    plp
    rtl
@convert:
    rep #$20
    .a16
    .repeat 16, color
        .if (color & 3) = 0
            ; All BG transparent colors use final canonical universal color.
            lda f:$7E0120
        .else
            lda f:$7E0110+color
        .endif
        and #$003F
        asl
        tax
        lda f:$C00000+native_palette,x
        sta f:$7E5400+color*2
    .endrepeat
    .repeat 16, color
        .if (color & 3) = 0
            ; These physical shadow slots are not written by the original
            ; palette copy: transparent sprite entries alias BG instead.
            lda f:$7F3F10+color
        .else
            lda f:$7E0120+color
        .endif
        and #$003F
        asl
        tax
        lda f:$C00000+native_palette,x
        sta f:$7E5500+(color / 4)*32+(color & 3)*2
    .endrepeat
    sep #$20
    .a8
    lda #1
    sta a:$1CED
    jmp @return
.ifdef EXPERIMENTAL_PENDING_PALETTE_WRITE_HEAD
.include "pending_palette_queue.inc"
.endif
