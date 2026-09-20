; Current early publisher: A8/I16, DB=0, D=$1E00. Preserve old exit A/X/Y.
; First upload and every hidden transition remain full544 bytes. Visible
; updates subsequently transfer only64 live slots; current producer leaves
; unused slots/high table static. $1BF0 is cleared by the existing WRAM reset.
.setcpu "65816"
EXPERIMENTAL_OAM_LIVE_HALF = 1
.include "oam_live_half.inc"
.a8
.i16
.segment "CODE"
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
    lda $1CA0
    bne full
    select_oam_transfer_size
full:
    stx $4305
    lda #1
    sta $420B
    complete_oam_transfer
    ldx #544
    lda #$80
    sta $2115
    rts
