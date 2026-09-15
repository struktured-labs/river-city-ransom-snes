; Producer: E=0, A16/X16, DB=0, D=$1E00. No hardware PPU writes.
; Called after original game interrupt work / PPUMASK writes, never by the
; bounded SNES VBlank consumer. Caller masks NMI for the native-mode bridge.
; Row flags: bit0=shadow dirty, bit1=immutable staged row ready for DMA.
; State 3 must drain the old staged row before preparing the newer shadow.
native_prepare:
    ; A background pattern-table change invalidates each staged tile's bit 8.
    sep #$20
    .a8
    lda $1C20
    and #$10
    cmp $1C78
    beq @rows_start
    sta $1C78
    lda #1
    sta $1C85
    ldx #0
    lda #1
@invalidate:
    sta $1D00,x
    inx
    cpx #128
    bne @invalidate
@rows_start:
    lda $1C79
    beq @scan_rows
    lda $1C85
    bne @scan_rows
    jmp prepare_palette
@scan_rows:
    stz $1C85
    rep #$20
    .a16
    lda $1C76
    and #$007F
    tax
    sep #$20
    .a8
    ; Four rows for menu/load work; gameplay retains its two-row budget.
    lda $0100
    and #$C0
    cmp #$C0
    beq @game_budget
    lda #4
    bra @set_budget
@game_budget:
    lda #2
@set_budget:
    sta $1C6B
    lda #128
    sta $1C6C
@rows:
    sep #$20
    .a8
    lda $1D00,x
    cmp #1
    beq @convert
@next:
    inx
    cpx #128
    bcc :+
    ldx #0
:
    dec $1C6C
    beq @prepared
    lda $1C6B
    bne @rows
@prepared:
    txa
    sta $1C76
    jmp prepare_palette
@convert:
    rep #$20
    .a16
    stx $14
    txa
    and #$0060
    xba
    lsr
    lsr
    lsr
    ora #$2000
    sta $00
    clc
    adc #$03C0
    sta $04
    txa
    and #$0060
    xba
    lsr
    lsr
    sta $16
    sep #$20
    .a8
    lda #$7F
    sta $02
    sta $06
    rep #$20
    .a16
    txa
    and #$001F
    cmp #30
    bcc :+
    sep #$20
    .a8
    stz $1D00,x
    jmp @next
:
    .a16
    asl
    asl
    asl
    asl
    asl
    tay
    asl
    clc
    adc $16
    tax
    lda $1C20
    and #$0010
    asl
    asl
    asl
    asl
    sta $0E                 ; pattern-half tile bit, constant across the row
    lda $14
    and #$001C
    asl
    sta $10                 ; first attribute byte for this tile row
    lda $14
    and #2
    sta $12                 ; bottom half of the attribute quadrant
    lda #8
    sta $18                 ; eight groups of four tiles
@group:
    phy
    ldy $10
    lda [$04],y
    and #$00FF
    sta $0C
    lda $12
    beq :+
    lda $0C
    lsr
    lsr
    lsr
    lsr
    sta $0C
:
    ply
    .repeat 2, pair
        lda $0C
        .if pair
            lsr
            lsr
        .endif
        and #3
        xba
        asl
        asl
        ora $0E
        sta $0A
        .repeat 2
            lda [$00],y
            and #$00FF
            ora $0A
            sta f:$7E3000,x
            inx
            inx
            iny
        .endrepeat
    .endrepeat
    inc $10
    dec $18
    bne @group
    ldx $14
    sep #$20
    .a8
    lda #2
    sta $1D00,x
    dec $1C6B
    bne :+
    lda #1
    sta $1C85              ; work beyond this call's row budget may remain
:
    jmp @next
prepare_palette:
    ; Compare the actual shadow, not write flags: original code may rewrite
    ; identical palettes every frame. The first publication always converts.
    lda $1C79
    beq @changed
    rep #$20
    .a16
    ldx #0
@compare:
    lda f:$7F3F00,x
    cmp f:$7E5580,x
    bne @snapshot
    inx
    inx
    cpx #32
    bne @compare
    sep #$20
    .a8
    jmp prepare_sprites
@changed:
    rep #$20
    .a16
@snapshot:
    ldx #0
@copy:
    lda f:$7F3F00,x
    sta f:$7E5580,x
    inx
    inx
    cpx #32
    bne @copy
    sep #$20
    .a8
    ldy #0
@bg:
    tya
    and #3
    bne :+
    lda f:$7F3F00
    bra @color
:
    tyx
    lda f:$7F3F00,x
@color:
    jsr native_color
    .a16
    sta $08
    tya
    asl
    tax
    lda $08
    sta f:$7E5400,x
    sep #$20
    .a8
    iny
    cpy #16
    bne @bg
    ldy #0
@obj:
    tyx
    lda f:$7F3F10,x
    jsr native_color
    .a16
    sta $08
    tya
    and #12
    asl
    asl
    asl
    sta $0A
    tya
    and #3
    asl
    ora $0A
    tax
    lda $08
    sta f:$7E5500,x
    sep #$20
    .a8
    iny
    cpy #16
    bne @obj
prepare_sprites:
    lda $1C79
    beq @changed
    lda $1C20
    and #8
    cmp $1C86
    bne @changed
    rep #$20
    .a16
    ldx #0
@compare:
    lda $1000,x
    cmp f:$7E5600,x
    bne @snapshot
    inx
    inx
    cpx #256
    bne @compare
    sep #$20
    .a8
    jmp prepare_tail
@changed:
    rep #$20
    .a16
@snapshot:
    ; Native block copy is safe inside the already-masked producer bridge.
    phb
    ldx #$1000
    ldy #$5600
    lda #255
    mvn $7E0000,$7E0000
    plb
    sep #$20
    .a8
    lda $1C20
    and #8
    sta $1C86
    ; 8x8 NES sprites, preserved ordering, flips and palette indices.
    ldx #0
@sprites:
    lda $1003,x
    sta f:$7E5000,x
    lda $1000,x
    cmp #239
    bcc @visible_sprite
    lda #240
    bra @sprite_y
@visible_sprite:
    clc
    adc #2
@sprite_y:
    sta f:$7E5001,x
    lda $1001,x
    sta f:$7E5002,x
    lda $1002,x
    and #$C0
    sta $08
    lda $1002,x
    and #$20
    bne :+
    lda $08
    ora #$30
    sta $08
:
    lda $1002,x
    and #3
    asl
    ora $08
    sta $08
    lda $1C20
    and #8
    lsr
    lsr
    lsr
    ora $08
    sta f:$7E5003,x
    inx
    inx
    inx
    inx
    cpx #256
    bne @sprites
    lda $1C79
    bne prepare_tail
@hidden:
    lda #240
    sta f:$7E5001,x
    inx
    inx
    inx
    inx
    cpx #512
    bne @hidden
    ldx #0
@high_oam:
    lda #0
    sta f:$7E5200,x
    inx
    cpx #32
    bne @high_oam

prepare_tail:
    jsr prepare_chr
    lda #1
    sta $1C79
    rep #$20
    .a16
    rts

native_color:
    ; A8 palette index -> A16 RGB555; X clobbered, Y retained.
    .a8
    and #$3F
    rep #$20
    .a16
    and #$00FF
    asl
    tax
    lda native_palette,x
    rts

prepare_chr:
    .a8
    ldy #0
@slot:
    sty $18
    rep #$20
    .a16
    tya
    ; MMC3 CHR inversion changes which registers feed a physical PPU slot,
    ; not the destination slot. The CPU-side CHR reader already honors it.
    pha
    lda $1C19
    and #$0080
    beq :+
    pla
    eor #4
    bra @mapped_slot
:
    pla
@mapped_slot:
    sta $10
    cmp #4
    bcs @single
    lsr
    tax
    lda $1C10,x
    and #$00FE
    sta $12
    lda $10
    and #1
    ora $12
    bra @bank
@single:
    sec
    sbc #2
    tax
    lda $1C10,x
    and #$007F
@bank:
    and #$007F
    sta $12
    ; BG job = slot. Only queue the selected background pattern half.
    tya
    tax
    sep #$20
    .a8
    tya
    and #4
    asl
    asl
    eor $1C20
    and #$10
    bne @no_bg
    lda $12
    cmp $1DA0,x
    beq @obj
    sta $1DA0,x
    lda #1
    sta $1D80,x
    rep #$20
    .a16
    txa
    asl
    asl
    asl
    tax
    lda $12
    xba
    asl
    asl
    sta $1500,x
    lda $12
    lsr
    lsr
    lsr
    lsr
    lsr
    lsr
    clc
    adc #$00C9
    sta $1502,x
    tya
    xba
    asl
    sta $1504,x
    lda #1024
    sta $1506,x
    sep #$20
    .a8
    bra @obj
@no_bg:
    lda #$FF
    sta $1DA0,x
    stz $1D80,x
@obj:
    rep #$20
    .a16
    tya
    asl
    clc
    adc #8
    tax
    sep #$20
    .a8
    tya
    and #4
    asl
    eor $1C20
    and #8
    bne @no_obj
    lda $12
    cmp $1DA0,x
    beq @next
    sta $1DA0,x
    sta $1DA1,x
    lda #1
    sta $1D80,x
    stz $1D81,x
    rep #$20
    .a16
    txa
    asl
    asl
    asl
    tax
    lda $12
    xba
    asl
    asl
    asl
    sta $1500,x
    clc
    adc #1024
    sta $1508,x
    lda $12
    lsr
    lsr
    lsr
    lsr
    lsr
    clc
    adc #$00CB
    sta $1502,x
    sta $150A,x
    tya
    xba
    asl
    asl
    clc
    adc #$4000
    sta $1504,x
    clc
    adc #512
    sta $150C,x
    lda #2048
    sta $1506,x
    sep #$20
    .a8
    bra @next
@no_obj:
    lda #$FF
    sta $1DA0,x
    sta $1DA1,x
    stz $1D80,x
    stz $1D81,x
@next:
    ldy $18
    iny
    cpy #8
    beq :+
    jmp @slot
:
    rts
native_palette:
    .include "native_palette.inc"
