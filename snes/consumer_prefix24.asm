; Same ring order and visit budget as suffix-hybrid. A wrapped bounded search
; from zero can inspect its first24 flags without three indexed OR reductions.
; All word probes remain within both the queue and remaining visit budget.
.setcpu "65816"
.a16
.i16
.segment "CODE"
    rep #$20
suffix_loop:
    txa
    and #1
    beq even_start
    sep #$20
    .a8
    lda $1D00,x
    and #2
    beq odd_empty
    jmp $83D7
odd_empty:
    inx
    dey
    bne odd_more
    cpx #128
    bcc suffix_finish
    ldx #0
suffix_finish:
    jmp $844F
odd_more:
    cpx #128
    bcc :+
    ldx #0
:
    rep #$20
    .a16
even_start:
    stx $1C
    tya
    clc
    adc $1C
    cmp #128
    bcs suffix_start
    jmp bounded
suffix_start:
    lda #$0202
    jmp (entries,x)
suffix_found:
    lda $1D00,x
    and #2
    bne :+
    inx
:
    txa
    sec
    sbc $1C
    sta $1C
    tya
    sec
    sbc $1C
    tay
    sep #$20
    .a8
    jmp $83D7
    .a16
suffix_empty:
    lda #128
    sec
    sbc $1C
    sta $1C
    tya
    sec
    sbc $1C
    tay
    ldx #0
    cpy #0
    beq suffix_finish
    jmp suffix_loop
bounded:
    cpx #0
    bne fallback
    cpy #24
    bcc fallback
    jmp prefix24
fallback:
    .include "consumer_tail_loop.asm"
    .a16
prefix24:
    lda #$0202
    .repeat 12, pair
        bit a:$1D00 + pair*2
        beq :+
        ldx #pair*2
        jmp suffix_found
:
    .endrepeat
    ldx #24
    tya
    sec
    sbc #24
    tay
    bne :+
    jmp $844F
:
    jmp fallback
entries:
    .repeat 64, pair
        .word search + pair*11
    .endrepeat
search:
    .repeat 64, pair
        bit a:$1D00 + pair*2
        beq :+
        ldx #pair*2
        jmp suffix_found
:
    .endrepeat
    jmp suffix_empty
