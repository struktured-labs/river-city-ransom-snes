; E=0/A16/I16, D=NES source page, NMI already masked. Replaces the unrolled
; low-WRAM OAM copy. One source load serves shadow copy AND incremental render.
; C=0 means conversion complete; C=1 requests the original post-copy helper.
; C is dead at the old copy site (SEC/XCE follows); MVN fallback already has C=1.
.setcpu "65816"
.a16
.i16
.segment "CODE"
.export sprite_fused_copy
sprite_fused_copy:
    php
    phx
    phy
    phb
    sep #$20
    .a8
    lda #$7E
    pha
    plb
    rep #$20
    .a16
    tdc
    cmp #$0200             ; only original sprite page; other pages keep copy ABI
    beq :+
    jmp fallback
:
    sep #$20
    .a8
    lda a:$1C79
    bne :+
    jmp fallback
:
    lda a:$1CA0
    beq :+
    jmp fallback
:
    lda a:$1C20
    and #8
    cmp a:$1C86
    beq :+
    jmp fallback
:
    lsr
    lsr
    lsr
    sta a:$1E08
    rep #$20
    .a16
    ldy #0
    ; Direct page retains the page-aligned original source, NOT producer DP.
    .repeat 64, sprite
    .scope
    lda z:sprite*4
    sta a:$1000 + sprite*4
    cmp a:$5600 + sprite*4
    beq attribute_x
    sta a:$5600 + sprite*4
    and #$00FF
    tax
    sep #$20
    .a8
    iny
    lda f:$C00000 + SPRITE_Y_MAP,x
    sta a:$5001 + sprite*4
    lda z:sprite*4+1
    sta a:$5002 + sprite*4
    rep #$20
    .a16
attribute_x:
    lda z:sprite*4+2
    sta a:$1002 + sprite*4
    cmp a:$5602 + sprite*4
    beq next
    sta a:$5602 + sprite*4
    and #$00FF
    tax
    sep #$20
    .a8
    iny
    lda f:$C00000 + SPRITE_ATTR_MAP,x
    ora a:$1E08
    sta a:$5003 + sprite*4
    lda z:sprite*4+3
    sta a:$5000 + sprite*4
    rep #$20
    .a16
next:
    .endscope
    .endrepeat
    sep #$20
    .a8
    tya
    beq :+
    lda #1
    sta a:$1CEE
:
    stz a:$1C87
    rep #$30
    .a16
    .i16
    plb
    ply
    plx
    plp
    lda z:$FE               ; exact original final copied word
    clc
    rtl
fallback:
    rep #$20
    .a16
    .repeat 128, word
        lda z:word*2
        sta a:$1000 + word*2
    .endrepeat
    plb
    ply
    plx
    plp
    lda z:$FE
    sec
    rtl
