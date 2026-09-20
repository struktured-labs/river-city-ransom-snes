; Exact-count stride32 command copy. E=1/A8/X8; no new WRAM scratch.
; Unsupported/decimal/palette/long commands retain the entire old routine.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export ring_stride_cache
ring_stride_cache:
    php
    pha
    php
    pla
    and #8
    bne fallback
    lda a:$1C20
    and #4
    beq fallback
    cpy #0
    beq fallback
    cpy #33
    bcs fallback
    lda a:$1C27
    cmp #$20
    bcc fallback
    cmp #$3B
    bcs fallback
    pla
    plp
    php
    phd
    stz $4200
    lda #$1B
    xba
    lda #0
    tcd
    jsr PPU_POINTER
next_byte:
    lda a:$0545,x
    cmp [$00]
    beq unchanged
    sta [$00]
    phx
    jsr MARK_DIRTY
    plx
unchanged:
    inc a:$1C09
    inx
    txa
    and #$3F
    tax
    lda a:$1C26
    clc
    adc #32
    sta a:$1C26
    bcc same_page
    inc a:$1C27
    dey
    beq finished
    jsr PPU_POINTER
    bra next_byte
same_page:
    dey
    beq finished
    ; Ordinary CIRAM mapping preserves the low byte. Re-resolve its physical
    ; page on carry; skip the final pointer update to match the old scratch.
    sta $00
    bra next_byte
finished:
    jmp OLD_DONE
fallback:
    pla
    plp
    ; Replay the five overwritten bytes, then continue old body unchanged.
    php
    phd
    stz $4200
    jmp OLD_BODY
