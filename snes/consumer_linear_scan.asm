; CHR-restored3527: fast empty-span search, without a new queue or priority.
; Only scan the non-wrapping suffix when its entire length fits Y's budget.
; Odd starts / shorter budgets take the original eight-row/scalar search.
; Entry A may be8/16; X/Y16, DB=0, DP=$1E00. $1C is beam-check scratch.
.setcpu "65816"
.a16
.i16
.segment "CODE"
    rep #$20
    txa
    and #1
    bne fallback
    stx $1C
    tya
    clc
    adc $1C
    cmp #128
    bcc fallback
    lda #$0202
    jmp (entries,x)
fallback:
    sep #$20
    .a8
    cpx #121
    jmp $83A3                 ; original BCS scalar / CPY #8 ...
.a16
found:
    lda $1D00,x
    and #2
    bne :+
    inx                       ; only the high byte of this pair is ready
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
    jmp $83D9                 ; original scalar LDA flags,X / AND #2
.a16
empty:
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
    beq finish
    jmp $839E
finish:
    jmp $844F
entries:
    ; X is an even row index, so it directly indexes 16-bit jump addresses.
    .repeat 64, pair
        .word search + pair*11
    .endrepeat
search:
    .repeat 64, pair
        bit a:$1D00 + pair*2
        beq :+
        ldx #pair*2
        jmp found
:
    .endrepeat
    jmp empty
