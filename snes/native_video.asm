; Native SNES publication of the software NES PPU/OAM state.
; Called with native A16/X16, DB=0, D=$1E00 and NMI disabled.
; This first integration publishes a single nametable (menu/logo workload).
native_video:
    sep #$20
    .a8
    stz $2105
    stz $2106
    stz $210B
    stz $210C
    stz $2123
    stz $2124
    stz $2125
    stz $212E
    stz $212F
    lda #$20
    sta $2107
    lda #2
    sta $2101
    stz $210D
    stz $210D
    lda #$FF
    sta $210E
    sta $210E
    lda #$80
    sta $2115
    ; Keep the last frame visible while preparing updates. Only a CHR bank
    ; change needs a larger forced-blank transfer in this initial publisher.
    ldx #0
@check_chr:
    lda $1C10,x
    cmp $1C40,x
    bne @reload_chr
    inx
    cpx #6
    bne @check_chr
    lda $1C46
    beq @reload_chr
    rep #$20
    .a16
    jmp @nametable
@reload_chr:
    .a8
    lda #$80
    sta $2100
    ldx #0
@remember_chr:
    lda $1C10,x
    sta $1C40,x
    inx
    cpx #6
    bne @remember_chr
    lda #1
    sta $1C46
    ; CHR source banks. MMC3 mode 0 observed in the logo/menu workload.
    rep #$20
    .a16
    ldx #0
@chr:
    stx $10
    txa
    cmp #4
    bcs @single
    lsr
    tay
    lda $1C10,y
    and #$00FE
    sta $12
    txa
    and #1
    ora $12
    bra @bank
@single:
    sec
    sbc #2
    tay
    lda $1C10,y
    and #$00FF
@bank:
    and #$007F
    sta $12
    ; BG 2bpp: C9/CA banks, 1 KiB source → 1 KiB VRAM.
    lsr
    lsr
    lsr
    lsr
    lsr
    lsr
    clc
    adc #$00C9
    sep #$20
    .a8
    sta $4304
    lda #1
    sta $4300
    lda #$18
    sta $4301
    rep #$20
    .a16
    lda $12
    xba
    asl
    asl
    sta $4302
    lda $10
    xba
    asl
    sta $2116
    lda #1024
    sta $4305
    sep #$20
    .a8
    lda #1
    sta $420B
    ; OBJ 4bpp: CB..CE banks, 1 KiB original → 2 KiB VRAM.
    rep #$20
    .a16
    lda $12
    lsr
    lsr
    lsr
    lsr
    lsr
    clc
    adc #$00CB
    sep #$20
    .a8
    sta $4304
    rep #$20
    .a16
    lda $12
    xba
    asl
    asl
    asl
    sta $4302
    lda $10
    xba
    asl
    asl
    clc
    adc #$4000
    sta $2116
    lda #2048
    sta $4305
    sep #$20
    .a8
    lda #1
    sta $420B
    rep #$20
    .a16
    ldx $10
    inx
    cpx #8
    beq :+
    jmp @chr
:
@nametable:
    ; Long pointers to the currently selected NES nametable and its attributes.
    lda $1C20
    and #3
    xba
    asl
    asl
    clc
    adc #$2000
    sta $00
    clc
    adc #$03C0
    sta $04
    sep #$20
    .a8
    lda #$7F
    sta $02
    sta $06
    rep #$20
    .a16
    ldx #0
@tile:
    txa
    tay
    lda [$00],y
    and #$00FF
    sta $08
    lda $1C20
    and #$0010
    beq :+
    lda $08
    ora #$0100
    sta $08
:
    txa
    lsr
    lsr
    lsr
    lsr
    and #$0038
    sta $0A
    txa
    and #$001F
    lsr
    lsr
    ora $0A
    tay
    lda [$04],y
    and #$00FF
    sta $0C
    txa
    and #$0040
    lsr
    lsr
    lsr
    lsr
    sta $0A
    txa
    and #2
    ora $0A
    tay
    lda $0C
    cpy #0
    beq @shifted
@shift:
    lsr
    dey
    bne @shift
@shifted:
    and #3
    xba
    asl
    asl
    ora $08
    phx
    pha
    txa
    asl
    tax
    pla
    sta f:$7E3000,x
    plx
    inx
    cpx #960
    bne @tile
    sep #$20
    .a8
@visible:
    lda $4212
    bmi @visible
@blank:
    lda $4212
    bpl @blank
    rep #$20
    .a16
    lda #1
    sta $4300              ; mode 1, target $2118 restored below
    sep #$20
    .a8
    lda #$18
    sta $4301
    rep #$20
    .a16
    lda #$2000
    sta $2116
    lda #$3000
    sta $4302
    lda #2048
    sta $4305
    sep #$20
    .a8
    lda #$7E
    sta $4304
    lda #1
    sta $420B
    ; Palette conversion uses a pinned RGB table reduced to RGB555.
    stz $2121
    ldy #0
@bg_palette:
    tya
    and #3
    bne :+
    lda f:$7F3F00
    bra @bg_color
:
    tyx
    lda f:$7F3F00,x
@bg_color:
    jsr native_color
    iny
    cpy #16
    bne @bg_palette
    ldy #0
@obj_palette:
    tya
    and #3
    bne :+
    tya
    asl
    asl
    clc
    adc #128
    sta $2121
:
    tyx
    lda f:$7F3F10,x
    jsr native_color
    iny
    cpy #16
    bne @obj_palette
    ; 8x8 NES sprites, preserved ordering, flips and palette indices.
    ldx #0
@sprites:
    lda $1003,x
    sta f:$7E3800,x
    lda $1000,x
    clc
    adc #2
    sta f:$7E3801,x
    lda $1001,x
    sta f:$7E3802,x
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
    sta f:$7E3803,x
    inx
    inx
    inx
    inx
    cpx #256
    bne @sprites
@hidden:
    lda #240
    sta f:$7E3801,x
    inx
    inx
    inx
    inx
    cpx #512
    bne @hidden
    ldx #0
@high_oam:
    lda #0
    sta f:$7E3A00,x
    inx
    cpx #32
    bne @high_oam
    stz $2102
    stz $2103
    stz $4300
    lda #4
    sta $4301
    ldx #$3800
    stx $4302
    ldx #544
    stx $4305
    lda #1
    sta $420B
    lda $1C21
    and #8
    lsr
    lsr
    lsr
    sta $08
    lda $1C21
    and #$10
    ora $08
    sta $212C
    lda #$0F
    sta $2100
    rep #$20
    .a16
    rts

native_color:
    ; Input A8 NES palette number; X clobbered, Y retained.
    .a8
    and #$3F
    rep #$20
    .a16
    and #$00FF
    asl
    tax
    lda native_palette,x
    sep #$20
    .a8
    sta $2122
    xba
    sta $2122
    rts
native_palette:
    .include "native_palette.inc"
