; Asset-free producer/NMI consumer test: red BG tile and blue OBJ tile.
.setcpu "65816"
.macpack longbranch
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
    ldx #$1FFF
    txs
    sep #$20
    .a8
    pha
    plb
    stz $4200
    stz $420B
    stz $420C
    lda #$80
    sta $2100
    ldx #0
@clear:
    lda #0
    sta f:$7E0000,x
    sta f:$7F0000,x
    inx
    bne @clear
    stz $2105
    stz $210B
    stz $210C
    stz $212C
    stz $212D
    stz $2130
    stz $2131
    lda #4
    sta $2133
    lda #$20
    sta $2107
    lda #2
    sta $2101
    stz $210D
    stz $210D
    lda #$FF
    sta $210E
    sta $210E
    ldx #0
@cache:
    sta $1DA0,x
    inx
    cpx #24
    bne @cache
    ldx #0
@hide:
    sta $1000,x
    inx
    inx
    inx
    inx
    cpx #256
    bne @hide
    lda #15
    sta $1000
    lda #1
    sta $1001
    lda #16
    sta $1003
    lda #8
    sta $1C20
.ifdef LEFT_MASK
    lda #(LEFT_MASK ^ 6)  ; begin with opposite clipping, then change it live
.else
    lda #$1E             ; this fixture intentionally draws at x=0
.endif
    sta $1C21
    lda #1
    sta f:$7F2000
    sta f:$7F3F01
    sta $1D00
    lda #2
    sta f:$7F3F11
    rep #$20
    .a16
    lda #$1E00
    tcd
    jsr native_prepare
    sep #$20
    .a8
    ; A newer shadow write must not revoke an already prepared row's DMA.
    lda #3
    sta $1D00
    lda #5
    sta $1C61
    lda #$80
    sta $4200
@wait:
    lda $1C04
    cmp #60
    bcc @wait
    lda $1C7B
    jne failed
    lda $1D00
    cmp #1
    jne failed
    lda $1C85
    cmp #1
    jne failed
    ; Second generation: nonadjacent dirty rows and moved OAM must drain too.
    stz $4200
    ; Cache invalidation must depend on palette bytes and the sprite pattern
    ; bit, even when the OAM source itself is unchanged.
    lda #7
    sta $1C61
    lda #2
    sta f:$7F3F01
    rep #$20
    .a16
    jsr native_prepare
    lda f:$7E5402
    cmp #$7C00
    jne failed
    sep #$20
    .a8
    lda #1
    sta f:$7F3F01
    stz $1C20
    rep #$20
    .a16
    jsr native_prepare
    lda f:$7E5402
    cmp #$001F
    jne failed
    sep #$20
    .a8
    lda f:$7E5003
    and #1
    jne failed
    lda #8
    sta $1C20
    rep #$20
    .a16
    jsr native_prepare
    sep #$20
    .a8
    lda f:$7E5003
    and #1
    cmp #1
    jne failed
    lda #1
    sta f:$7F20E0
    sta f:$7F2300
    sta $1D07
    sta $1D18
    sta $1C85
.ifdef LEFT_MASK
    lda #LEFT_MASK
    sta $1C21
    lda #4               ; straddle the eight-pixel window boundary
.else
    lda #32
.endif
    sta $1003
    lda #$18
    sta $1C20
.ifdef SCROLL_TEST
    ; Poison the relocated direct-page aliases: game camera bytes are in
    ; absolute low WRAM, not in the renderer's D=$1E00 scratch page.
    lda #$40
    sta a:$1EF6
    sta a:$1EDE
    sta a:$1EDF
    lda #1
    sta a:$1E3D
    lda #$C0
    sta $0100
    lda #8
    sta a:$00F6
    lda #1
    sta f:$7F24E0
    sta f:$7F2700
    sta $1D27
    sta $1D38
.endif
    rep #$20
    .a16
    jsr native_prepare
    sep #$20
    .a8
    lda #6
    sta $1C61
    lda #$80
    sta $4200
@wait_second:
    lda $1C04
    cmp #120
    bcs @ready_second
    wai
    stz $4200
    rep #$20
    .a16
    jsr native_prepare
    sep #$20
    .a8
@outside_blank:
    lda $4212
    bmi @outside_blank
    lda #$80
    sta $4200
    bra @wait_second
@ready_second:
    lda $1C85
    bne failed
    lda $1C7B
    bne failed
    lda $1D07
    ora $1D18
    bne failed
    ldx #0
@queue:
    lda $1D80,x
    bne failed
    inx
    cpx #24
    bne @queue
.ifdef LAST_CHR_TEST
    ; Only the final queue byte is set. Erase active tile 257, then require slot 23
    ; to restore it from synthetic CHR ROM before the final pixel oracle.
    stz $4200
    lda #8
    sta $1C61
    lda #$80
    sta $2100
    sta $2115
    ldx #$0808
    stx $2116
    ldx #8
@erase_tile:
    stz $2118
    stz $2119
    dex
    bne @erase_tile
    ldx #$0010
    stx $15B8
    lda #$C9
    sta $15BA
    ldx #$0808
    stx $15BC
    ldx #16
    stx $15BE
    lda #1
    sta $1D97
@outside_last:
    lda $4212
    bmi @outside_last
    lda #$80
    sta $4200
@wait_last:
    lda $1C04
    cmp #136
    bcc @wait_last
    lda $1D97
    jne failed
.endif
    lda #1
    sta $1C60
@idle:
    wai
    bra @idle
failed:
    sep #$20
    .a8
    lda #$EE
    sta $1C60
    bra failed
nmi:
    rep #$30
    .a16
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
    lda $4210
.ifdef LATE_TEST
    ; Defer the first consumer to line 260, like a completed bank switch.
    ; It must leave the immutable queued row intact and avoid all DMA.
    lda $1C04
    ora $1C05
    bne @ordinary
@late_wait:
    lda $2137
    lda $213D
    sta $1C7C
    lda $213D
    and #1
    beq @late_wait
    lda $1C7C
    cmp #4
    bcc @late_wait
    jsr native_video
    lda $1D00
    cmp #3
    jne failed
    lda $1C7B
    jne failed
    bra @consumed
@ordinary:
.endif
    jsr native_video
.ifdef LATE_TEST
@consumed:
.endif
    rep #$20
    .a16
    inc $1C04
    inc $1C62
    plb
    pld
    ply
    plx
    pla
    rti
interrupt:
    rti
.include "native_video.asm"
.include "native_prepare.asm"
.segment "HEADER"
    .byte "RCR NMI VIDEO TEST  "
    .byte $20
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,nmi,0,interrupt
    .word 0,0,interrupt,0,nmi,nmi,reset,interrupt
