; Asset-free actual-VRAM/CGRAM oracle. Only BG1 is enabled: every normal
; renderer pixel must equal the independent observer. No game code involved.
.setcpu "65816"
.a8
.i16
.segment "CODE"
reset:
    sei
    clc
    xce
    rep #$38
    .a16
    lda #0
    tcd
    ldx #$1fff
    txs
    sep #$20
    .a8
    pha
    plb
    stz $4200
    stz $420b
    stz $420c
    lda #$80
    sta $2100
    lda #$80
    sta $2115
    ldx #0
    stx $2116
    lda #1
    sta $4300
    lda #$18
    sta $4301
    stx $4302
    lda #$c1
    sta $4304
    stx $4305
    lda #1
    sta $420b
    stz $2121
    stz $4300
    lda #$22
    sta $4301
    stx $4302
    lda #$c2
    sta $4304
    ldx #512
    stx $4305
    lda #1
    sta $420b
    lda #BG_MODE
    sta $2105
    lda #($40 | SC_SIZE)
    sta $2107
    lda #CHR_BASE
    sta $210b
    lda #<SCROLL_X
    sta $210d
    lda #>SCROLL_X
    sta $210d
    lda #<SCROLL_Y
    sta $210e
    lda #>SCROLL_Y
    sta $210e
    lda #WINDOW_ENABLE
    sta $2123
    stz $2124
    stz $2125
    stz $212d
    lda #WINDOW_LEFT
    sta $2126
    lda #WINDOW_RIGHT
    sta $2127
    lda #1
    sta $212e
    stz $212f
    stz $2130
    lda #COLOR_MATH
    sta $2131
    lda #4
    sta $2133
    lda #1
    sta $212c
    lda #BRIGHTNESS
    sta $2100
loop:
    bra loop
interrupt:
    rti
.segment "HEADER"
    .byte "RCR BG OBSERVER TEST "
    .byte $21,$00,$0b,$00,$01,$00,$00
    .word $ffff,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
