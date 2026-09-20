; Preserve exact queue order/budget. Use direct unrolled word probes only when
; the complete nonwrapping suffix fits the remaining visit budget. Short scans
; use the bounded mixed-group/tail scanner. No deadlines or persistent state.
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
    .include "consumer_tail_loop.asm"
    .a16
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
