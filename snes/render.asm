; Native hardware renderer test using original captured NES PPU/OAM state.
; A static test fixture, not a running copy of the NES game.
.setcpu "65816"
.a8
.i16
.include "snapshot.inc"
.segment "CODE"
reset:
    sei
    clc
    xce
    rep #$38
    .a16
    lda #0
    tcd
    ldx #$1FFF
    txs
    sep #$20
    .a8
    pha
    plb
    lda #$80
    sta $2100
    stz $4200
    stz $420B
    stz $420C
    stz $420D
    stz $2105
    stz $2106
    stz $210B
    stz $210C
    stz $2123
    stz $2124
    stz $2125
    stz $212D
    stz $212E
    stz $212F
    stz $2130
    stz $2131
    lda #$04                  ; 239-line overscan output
    sta $2133
    lda #$02                  ; OBJ patterns start at VRAM word $4000
    sta $2101
    lda #$20                  ; BG1 map starts at VRAM word $2000
    sta $2107
    lda #<SNAP_SCROLL_X
    sta $210D
    lda #>SNAP_SCROLL_X
    sta $210D
    lda #<SNAP_SCROLL_Y
    sta $210E
    lda #>SNAP_SCROLL_Y
    sta $210E
    lda #$80
    sta $2115
    ldx #0
    stx $2116
    ldx #.loword(bg)
    ldy #8192
    jsr dma_vram
    ldx #$4000
    stx $2116
    ldx #.loword(obj)
    ldy #16384
    jsr dma_vram
    ldx #$2000
    stx $2116
    ldx #.loword(tilemap)
    ldy #2048
    jsr dma_vram
    stz $2121
    stz $4300
    lda #$22
    sta $4301
    ldx #.loword(palette)
    stx $4302
    lda #1
    sta $4304
    ldx #512
    stx $4305
    lda #1
    sta $420B
    stz $2102
    stz $2103
    lda #$04
    sta $4301
    ldx #.loword(oam)
    stx $4302
    ldx #544
    stx $4305
    lda #1
    sta $420B
    lda #$11                  ; BG1 + OBJ, original patterns and palette indices
    sta $212C
    lda #$0F
    sta $2100
@halt:
    bra @halt

dma_vram:
    lda #1
    sta $4300
    sta $4304
    lda #$18
    sta $4301
    stx $4302
    sty $4305
    lda #1
    sta $420B
    rts
interrupt:
    rti

.segment "HEADER"
    .byte "RCR RENDER FIXTURE   "
    .byte $20, $00, $06, $00, $01, $00, $00
    .word $FFFF, $0000
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
.segment "ASSETS"
bg: .incbin "bg.bin"
obj: .incbin "obj.bin"
tilemap: .incbin "tilemap.bin"
palette: .incbin "palette.bin"
oam: .incbin "oam.bin"
