; Optional pre-boot splash. Original game code begins only after teardown.
; User-supplied Infidelity reveal: inverted BG1 window, right edge 0..252.
.setcpu "65816"
.a8
.i16
.segment "CODE"
entry:
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
    stz $212C
    stz $212D
    stz $2130
    stz $2131
    lda #4
    sta $2133
    lda #3
    sta $2105                ; BG1: indexed 8bpp, 8x8 tiles
    stz $2106
    stz $210B
    stz $210C
    lda #$70
    sta $2107                ; tilemap VRAM word $7000
    stz $210D
    stz $210D
    stz $210E
    stz $210E
    stz $2124
    stz $2125
    stz $2126
    stz $2127
    stz $2128
    stz $2129
    stz $212A
    stz $212B
    lda #3
    sta $2123                ; enable W1 + invert: mask OUTSIDE [0,right]
    lda #1
    sta $212C
    sta $212D
    sta $212E
    sta $212F
    lda #$80
    sta $2115
    ldx #0
    stx $2116
    ldx #.loword(tiles)
    ldy #tiles_end-tiles
    jsr dma_vram
    ldx #$7000
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
    ldx #512
    stx $4305
    lda #1
    sta $420B
.ifdef IDENT_AUDIO
    stz $1FF4               ; auditable SPC bootstrap/handoff error code
    jsr ident_upload
    bcc :+
    lda #$EE
    sta $1FF4
:
.endif
    lda #1
    sta $1FF0               ; observer phase; original reset clears this WRAM
    stz $1FF1
    jsr next_vblank
    lda #$0F
    sta $2100
@reveal:
    jsr next_vblank
    lda $1FF1
    cmp #$FC
    beq @hold
    clc
.ifdef WRONG_STEP
    adc #2
.else
    adc #4
.endif
    sta $1FF1
    sta $2127
    bra @reveal
@hold:
    lda #$FF                 ; FC is not full width: explicitly reveal final 3 px
    sta $1FF1
    sta $2127
    lda #2
    sta $1FF0
.ifdef IDENT_AUDIO
    ldx #0                   ; 240 uninterrupted pitch/volume updates, 3 bytes each
    stz $1FF2
    stz $1FF3
    ldy #240                 ; four seconds after the full image appears
.else
    ldx #180                 ; three seconds at 60 Hz: keep the full logo readable
.endif
@hold_frame:
    jsr next_vblank
.ifdef IDENT_AUDIO
    lda f:ident_curve,x
    sta $2140
    lda f:ident_curve+1,x
    sta $2141
    lda f:ident_curve+2,x
    sta $2143
    inc $1FF3               ; write sequence last: makes the 3-byte update atomic
    lda $1FF3
    sta $2142
    inx
    inx
    inx
    inc $1FF2
.endif
.ifdef IDENT_AUDIO
    dey
.else
    dex
.endif
    bne @hold_frame
.ifdef IDENT_AUDIO
    lda #$FF                ; key off, mute, and restore IPL for Memblers upload
    sta $2142
    jsr ident_wait_ipl
    bcc :+
    lda #$ED
    sta $1FF4
:
.endif
    lda #$80
    sta $2100
    stz $212C
    stz $212D
.ifndef DIRTY_WINDOW
    stz $2123
    stz $212E
    stz $212F
.endif
    stz $2126
    stz $2127
.ifdef DIAGNOSTIC_RULER
    ; Challenge cleanup with WH1=0: an enabled stale inverted window would
    ; leave only the leftmost column. Diagnostic only; absent in production.
    lda #1
    sta $212C
    lda #4
    sta $1FF0
    lda #$0F
    sta $2100
    jsr next_vblank
    lda #$80
    sta $2100
    stz $212C
.endif
    lda #5                   ; teardown in progress, distinct from challenge
    sta $1FF0
    stz $2105
    stz $2107
    stz $210D
    stz $210D
    stz $210E
    stz $210E
    ; Remove splash data. A fixed zero source clears all VRAM/CGRAM while blank.
    ldx #0
    stx $2116
    lda #9                   ; fixed source, mode 1 ($2118/$2119)
    sta $4300
    lda #$18
    sta $4301
    ldx #.loword(zero)
    stx $4302
    ldx #0                   ; DMA length zero means 65536 bytes
    stx $4305
    lda #1
.ifndef DIRTY_VRAM
    sta $420B
.endif
    stz $2121
    lda #8
    sta $4300
    lda #$22
    sta $4301
    ldx #512
    stx $4305
    lda #1
    sta $420B
    ; Remove our DMA register setup too; original boot owns all channels next.
    ldx #0
@clear_dma:
    stz $4300,x
    inx
    cpx #16
    bne @clear_dma
    lda #3                   ; one blank audit frame: VRAM must be fully clear
    sta $1FF0
    jsr next_vblank
    stz $1FF0
    stz $1FF1
    rep #$38
    .a16
    jml $C08005              ; original reset after SEI/CLC/XCE/REP #$38

.a8
next_vblank:
    lda $4212
    bmi next_vblank
@wait:
    lda $4212
    bpl @wait
    rts
dma_vram:
    lda #1
    sta $4300
    lda #$D1
    sta $4304
    lda #$18
    sta $4301
    stx $4302
    sty $4305
    lda #1
    sta $420B
    rts
.ifdef IDENT_AUDIO
ident_wait_port0:
    ldy #$FFFF
@poll:
    cmp $2140
    beq @ready
    dey
    bne @poll
    sec
    rts
@ready:
    clc
    rts
ident_wait_ipl:
    ldy #$FFFF
@poll:
    lda $2140
    cmp #$AA
    bne @again
    lda $2141
    cmp #$BB
    beq @ready
@again:
    dey
    bne @poll
    sec
    rts
@ready:
    clc
    rts
ident_upload:
    jsr ident_wait_ipl
    bcs @return
    ldx #$0200
    stx $2142
    lda #1
    sta $2141
    lda #$CC
    sta $2140
    jsr ident_wait_port0
    bcs @return
    ldx #0
@send:
    lda f:ident_spc,x
    sta $2141
    txa
    sta $2140
    jsr ident_wait_port0
    bcs @return
    inx
    cpx #ident_spc_end-ident_spc
    bne @send
    stz $2141
    ldy #$0200
    sty $2142
    inx
    inx
    txa
    sta $2140
    lda #$55
    jsr ident_wait_port0
@return:
    rts

; Every VBlank bends the pitch; one initial key-on, not 28 isolated bleeps.
ident_curve: .incbin "splash-ident-curve.bin"
ident_spc: .incbin "splash-ident-spc.bin"
ident_spc_end:
.endif
zero: .byte 0
.segment "CHR"
tiles: .incbin "splash-tiles.bin"
tiles_end:
.segment "MAP"
tilemap: .incbin "splash-map.bin"
.segment "PAL"
palette: .incbin "splash-palette.bin"
