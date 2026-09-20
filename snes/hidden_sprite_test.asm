.setcpu "65816"
.include "wram_clear.inc"
.a8
.i16
.segment "CODE"
reset:
    jml $C00000+fast_entry
fast_entry:
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
    lda #1
    sta $420D
    lda #$80
    sta $2100
    clear_wram_dma
    ldx #0
@seed:
    txa
    eor #SEED
    sta $1000,x
    lda #$CC
    sta f:$7E5600,x
    inx
    cpx #256
    bne @seed
    ldx #0
    lda #$55
@poison:
    sta f:$7E5000,x
    inx
    cpx #544
    bne @poison
    lda #INITIALIZED
    sta $1C79
    lda #STATE
    sta $1CA0
    lda #$18
    sta $1C21
    lda #HALF
    sta $1C20
    lda #1
    sta $1C87
    lda #CURSOR
    sta $1C76
    lda #ROW_FLAG
    sta $1D00+(CURSOR & 127)
    lda #REQUIRED
    sta $1E80+(CURSOR & 127)
    rep #$20
    .a16
    lda #$1E00
    tcd
    sep #$20
    .a8
    jsr prepare_sprites
    ; Snapshot first-call output, source cache and ownership latches.
    ldx #0
@snapshot:
    sep #$20
    .a8
    lda f:$7E5000,x
    sta f:$7E6000,x
    inx
    cpx #544
    bne @snapshot
    ldx #0
@snapshot_cache:
    lda f:$7E5600,x
    sta f:$7E6300,x
    inx
    cpx #256
    bne @snapshot_cache
    lda $1C87
    sta f:$7E6400
    lda $1C86
    sta f:$7E6401
.if PIPELINE
    ; The production consumer must remain hidden with an unqueued required
    ; row, even though this producer intentionally kept old OAM.
    jsr wait_vblank
    jsr native_video
    lda $1CA0
    sta f:$7E6402
.endif
    ; Complete-producer check after required background work is no longer
    ; unqueued. Do not change original sprite input between these calls.
.if PIPELINE
    lda #2
    sta $1D00+(CURSOR & 127)
.else
    stz $1D00+(CURSOR & 127)
    stz $1E80+(CURSOR & 127)
.endif
    jsr prepare_sprites
    sep #$20
    .a8
.if PIPELINE
    jsr wait_vblank
    jsr native_video
    lda $1CA0
    sta f:$7E6403
.else
    ; Upload the final snapshot through the real OAM port and read it back.
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
.endif
    stz $2102
    stz $2103
    ldx #0
@oam_read:
    lda $2138
    sta f:$7E6500,x
    inx
    cpx #544
    bne @oam_read
    lda #1
    sta $1C60
@visible:
    lda $4212
    bmi @visible
@blank:
    lda $4212
    bpl @blank
    inc $1C62
    bne @visible
    inc $1C63
    bra @visible
interrupt:
    rti
wait_vblank:
    lda $4212
    bmi wait_vblank
:
    lda $4212
    bpl :-
    rts
.if PIPELINE
.include "native_video.asm"
.endif
.include "native_prepare.asm"
.segment "HEADER"
    .byte "RCR HIDDEN OBJ TEST  "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
