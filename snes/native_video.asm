; Bounded NMI consumer. A8/X16, DB=0, D=$1E00.
; No conversion, no wait loops, no forced blank. Maximum 2048 VRAM bytes,
; 544 OAM bytes and 64 CGRAM bytes per invocation. Audio runs AFTER this.
native_video:
    .a8
    lda $1C79
    bne :+
    rts
:
    inc $1C7A
    lda $2137
    lda $213D
    sta $1C7C
    lda $213D
    and #1
    sta $1C7D
    lda #$80
    sta $2115
    lda #1
    sta $4300
    lda #$18
    sta $4301
    rep #$20
    .a16
    lda #2048
    sta $1A
    lda $1C75
    and #$00FF
    tax
    ldy #24
@chr:
    sep #$20
    .a8
    lda $1D80,x
    beq @next_chr
    rep #$20
    .a16
    lda $1A
    cmp #1024
    bcc @rows_start
    ; Preflight reserves room for up to 2 KiB plus the final palette/OAM batch.
    sep #$20
    .a8
    jsr dma_room
    bcc @rows_start
    stz $1D80,x
    rep #$20
    .a16
    phx
    txa
    asl
    asl
    asl
    tax
    lda $1500,x
    sta $4302
    lda $1504,x
    sta $2116
    sep #$20
    .a8
    lda $1502,x
    sta $4304
    rep #$20
    .a16
    lda $1506,x
    sta $4305
    sta $1E
    sep #$20
    .a8
    lda #1
    sta $420B
    rep #$20
    .a16
    lda $1A
    sec
    sbc $1E
    sta $1A
    plx
    inx
    cpx #24
    bcc :+
    ldx #0
:
    bra @rows_start
@next_chr:
    inx
    cpx #24
    bcc :+
    ldx #0
:
    dey
    bne @chr
@rows_start:
    sep #$20
    .a8
    txa
    sta $1C75
    rep #$20
    .a16
    lda $1C74
    and #$007F
    tax
    lda $1A
    bne :+
    jmp @finish
:
    ldy #32
@row:
    sep #$20
    .a8
    lda $1D00,x
    and #2
    beq @next_row
    rep #$20
    .a16
    lda $1A
    cmp #64
    bcc @finish
    sep #$20
    .a8
    ; Reserve enough time for the final palette/OAM batch after this small row.
    jsr row_room
    bcc @finish
    ; Consume the immutable staged row, retaining a newer shadow write.
    lda $1D00,x
    and #1
    sta $1D00,x
    rep #$20
    .a16
    txa
    asl
    asl
    asl
    asl
    asl
    pha
    clc
    adc #$2000
    sta $2116
    pla
    asl
    clc
    adc #$3000
    sta $4302
    lda #64
    sta $4305
    sep #$20
    .a8
    lda #$7E
    sta $4304
    lda #1
    sta $420B
    rep #$20
    .a16
    lda $1A
    sec
    sbc #64
    sta $1A
@next_row:
    inx
    cpx #128
    bcc :+
    ldx #0
:
    dey
    bne @row
@finish:
    sep #$20
    .a8
    txa
    and #$7F
    sta $1C74
    ; Publish prepared OAM.
    stz $2102
    stz $2103
    stz $4300
    lda #4
    sta $4301
    ldx #$5000
    stx $4302
    lda #$7E
    sta $4304
    ldx #544
    stx $4305
    lda #1
    sta $420B
    ; Only the 32 used palette colors, not all 256 CGRAM entries.
    stz $2121
    lda #$22
    sta $4301
    ldx #$5400
    stx $4302
    ldx #32
    stx $4305
    lda #1
    sta $420B
    .repeat 4, palette
        lda #$80+palette*16
        sta $2121
        ldx #$5500+palette*32
        stx $4302
        ldx #8
        stx $4305
        lda #1
        sta $420B
    .endrepeat
    lda $1C20
    and #2
    asl
    asl
    ora #$21                ; 64x32: adjacent NES nametables, not 32-tile wrap
    sta $2107
    lda $1C28
    sta $210D
    lda $1C20
    and #1
    sta $210D              ; nametable X select is scroll bit 8
    rep #$20
    .a16
    lda $1C29
    and #$00FF
    dec
    sta $08
    sep #$20
    .a8
    lda $08
    sta $210E
    lda $09
    sta $210E              ; preserve existing NES/SNES -1-line alignment
    ; RCR uses three horizontal bands: HUD, scrolling street, lower text.
    ; HDMA applies their scroll values at scanline boundaries independently
    ; of CPU game/audio service. Tables are rebuilt only during VBlank.
    stz $420C
    lda $0100
    and #$C0
    cmp #$C0
    bne @no_split
    lda #32
    sta $1C90
    lda a:$00DE
    sta $1C91
    stz $1C92
    lda #127
    sta $1C93
    lda #35
    sta $1C96
    lda a:$00F6
    sta $1C94
    sta $1C97
    lda a:$003D
    and #1
    sta $1C95
    sta $1C98
    lda #45
    sta $1C99
    lda a:$00DF
    sta $1C9A
    stz $1C9B
    stz $1C9C
    lda #2                 ; HDMA mode 2: two writes to BG1HOFS
    sta $4310
    lda #$0D
    sta $4311
    ldx #$1C90
    stx $4312
    lda #$7E
    sta $4314
    lda #2
    sta $420C
@no_split:
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
    ; Hardware assertion: consumer must not extend past VBlank.
    lda $2137
    lda $213D
    sta $1C7E
    lda $213D
    and #1
    sta $1C7F
    lda $4212
    bmi :+
    lda #1
    sta $1C7B
    lda $1C7E
    sta $1C68
    lda $1C7F
    sta $1C69
    lda $1C7C
    sta $1C6A
:
    rts

dma_room:
    ; A8, X/Y preserved. NTSC 239-line display: VBlank ends at scanline 262.
    ; Refuse CHR DMA after line 242, reserving the rest of VBlank for this
    ; whole-bank transfer and the final OAM/palette batch.
    lda $4212
    bpl @no
    lda $2137
    lda $213D
    sta $1C
    lda $213D
    and #1
    bne @no
    lda $1C
    cmp #243
    bcs @no
    sec
    rts
@no:
    clc
    rts

row_room:
    .a8
    lda $4212
    bpl @no
    lda $2137
    lda $213D
    sta $1C
    lda $213D
    and #1
    bne @no
    lda $1C
    cmp #247
    bcs @no
    sec
    rts
@no:
    clc
    rts
