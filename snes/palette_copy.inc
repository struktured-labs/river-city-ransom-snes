; E477 hook: preserve the original scalar path unless the complete palette
; copy is interrupt-owned, binary, X=0, at $3F00 with increment one.
palette_copy_loop:
    php
    cpx #0
    bne @fallback
    php
    pla
    and #8
    bne @fallback
    lda a:$1C26
    bne @fallback
    lda a:$1C27
    cmp #$3F
    bne @fallback
    lda a:$1C20
    and #4
    bne @fallback
    lda a:$1C0A
    ora a:$1C83
    bne @owned
    lda a:$1C20
    bpl @owned
@fallback:
    plp
    lda a:$0110,x
    jmp $E47A
@owned:
    stz $4200
    ; Original ascending write order matters: sprite transparent entries
    ; overwrite background entries 00/04/08/0C, not unused 10/14/18/1C.
    .repeat 32, color
        lda a:$0110+color
        .if color >= 16 .and (color & 3) = 0
            sta f:$7F3F00+color-16
        .else
            sta f:$7F3F00+color
        .endif
    .endrepeat
    sta a:$1B22
    lda #$1F
    sta a:$1B00
    lda #$3F
    sta a:$1B01
    lda #$7F
    sta a:$1B02
    lda #$20
    sta a:$1C26
    lda a:$1C09
    clc
    adc #32
    sta a:$1C09
    ; The scalar PPUDATA adapter leaves the hidden accumulator high byte
    ; equal to its direct-page high byte. Preserve that behavior too.
    lda #$1B
    xba
    plp
    lda a:$012F
    ldx #32
    cpx #32
    jmp $E482
