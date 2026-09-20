; Low tile bytes: 7E3000 + row*32. High bytes: 7E4000 + row*32.
; The whole pair is immutable until the consumer retires the row flag.
.macro planar_attribute_groups table, alias_store
    .repeat 8, group
        ldy $10
        lda [$04],y
        and #$00FF
        asl
        asl
        tax
        lda f:$C00000+table,x
        ora $0E
        sta $0A
        lda f:$C00000+table+2,x
        ora $0E
        sta $0C
        ldx $16
        ldy $1C
        lda $0A
        sta a:$4000+group*4,x
        .if alias_store
            sta a:$4000+group*4,y
        .endif
        lda $0C
        sta a:$4002+group*4,x
        .if alias_store
            sta a:$4002+group*4,y
        .endif
        inc $10
    .endrepeat
.endmacro

prepare_planar_row:
    .a16
    phb
    ; Both absolute destinations and low-memory variables are WRAM. Source
    ; nametables remain long indirect in 7F; lookup tables explicitly use C0.
    sep #$20
    .a8
    lda #$7E
    pha
    plb
    rep #$20
    .a16
    tya
    clc
    adc $00
    sta $1E
    lda $14
    .repeat 5
        asl
    .endrepeat
    sta $16
    lda $1C18
    and #1
    beq @vertical
    lda $14
    eor #$0020
    bra @alias
@vertical:
    lda $14
    eor #$0040
@alias:
    tax
    stx $1A
    .repeat 5
        asl
    .endrepeat
    sta $1C
    stz $18
    lda $1D00,x
    and #$00FF
    cmp #1
    bne :+
    inc $18
:
    ldx $1E
    lda $16
    clc
    adc #$3000
    tay
    lda #31
    mvn $7F0000,$7E0000
    lda $18
    beq :+
    ldx $1E
    lda $1C
    clc
    adc #$3000
    tay
    lda #31
    mvn $7F0000,$7E0000
:
    lda $0E
    xba
    ora $0E
    sta $0E                 ; pattern half as repeated high byte 0000/0101
    lda $18
    beq :+
    jmp planar_with_alias
:
    lda $12
    beq :+
    jmp planar_bottom
:
    planar_attribute_groups planar_palette_top, 0
    jmp planar_done
planar_bottom:
    planar_attribute_groups planar_palette_bottom, 0
    jmp planar_done
planar_with_alias:
    lda $12
    beq :+
    jmp planar_alias_bottom
:
    planar_attribute_groups planar_palette_top, 1
    jmp planar_alias_ready
planar_alias_bottom:
    planar_attribute_groups planar_palette_bottom, 1
planar_alias_ready:
    ldx $1A
    sep #$20
    .a8
    lda #2
    sta $1D00,x
    rep #$20
    .a16
planar_done:
    plb
    rts

planar_palette_top:
    .repeat 256, attribute
        .word (attribute & 3)*$0404, ((attribute >> 2) & 3)*$0404
    .endrepeat
planar_palette_bottom:
    .repeat 256, attribute
        .word ((attribute >> 4) & 3)*$0404, ((attribute >> 6) & 3)*$0404
    .endrepeat
