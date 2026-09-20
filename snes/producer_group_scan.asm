; Isolated experiment for CHR-restored3527. A8/X16, DB=0, DP=$1E00.
; Hook replaces LDA flags,X / CMP #1 at $8874; original BEQ is $8879.
; Preserve exact ring order and scan budget; ready-only rows may be skipped,
; but dirty+ready rows fall back and cannot overwrite immutable staging.
.setcpu "65816"
.a8
.i16
.segment "CODE"
    cpx #121
    bcs scalar
    lda $1C6C
    cmp #8
    bcc scalar
    rep #$20
    .a16
    lda $1D00,x
    ora $1D02,x
    ora $1D04,x
    ora $1D06,x
    and #$0101
    bne scalar_width
    txa
    clc
    adc #8
    tax
    cpx #128
    bcc :+
    ldx #0
:
    sep #$20
    .a8
    lda $1C6C
    sec
    sbc #8
    sta $1C6C
    beq prepared
    jmp $8872
scalar_width:
    sep #$20
    .a8
scalar:
    lda $1D00,x
    cmp #1
    jmp $8879
prepared:
    jmp $888E
