; Bounded nametable ring copy, E=1/A8/X8. No persistent new RAM.
; Cache the physical pointer for both increments; coalesce repeated dirtiness
; within one linear tile row / attribute group, preserving final scratch.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export ring_dirty_cache
ring_dirty_cache:
    php
    pha
    php
    pla
    and #8
    bne fallback
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
    lda $05
    pha
    stz $05
    jsr PPU_POINTER
    lda a:$1C20
    and #4
    bne vertical_byte
linear_byte:
    lda a:$0545,x
    cmp [$00]
    beq linear_unchanged
    sta [$00]
    lda $05
    bne linear_unchanged
    phx
    jsr mark_changed
    plx
    lda #1
    sta $05
linear_unchanged:
    inc a:$1C09
    inx
    txa
    and #$3F
    tax
    inc a:$1C26
    bne linear_same_page
    inc a:$1C27
    dey
    beq finished
    stz $05
    jsr PPU_POINTER
    bra linear_byte
linear_same_page:
    inc $00
    ; Every eight bytes is a conservative dirty-group boundary. Tile rows
    ; span32, attributes span8; both also reset at a logical page crossing.
    lda a:$1C26
    and #7
    bne :+
    stz $05
:
    dey
    bne linear_byte
    bra finished
fallback:
    pla
    plp
    php
    phd
    stz $4200
    jmp OLD_BODY
vertical_byte:
    lda a:$0545,x
    cmp [$00]
    beq vertical_unchanged
    sta [$00]
    phx
    jsr mark_changed
    plx
vertical_unchanged:
    inc a:$1C09
    inx
    txa
    and #$3F
    tax
    lda a:$1C26
    clc
    adc #32
    sta a:$1C26
    bcc vertical_same_page
    inc a:$1C27
    dey
    beq finished
    jsr PPU_POINTER
    bra vertical_byte
vertical_same_page:
    dey
    beq finished
    sta $00
    bra vertical_byte
finished:
    pla
    sta $05
    jmp OLD_DONE

; Eligibility guarantees nametable memory. Only the caller-visible RAM
; scratch must match MARK_DIRTY: caller X and flags are already saved.
mark_changed:
    lda a:$1C27
    and #3
    cmp #3
    bne tile
    lda a:$1C26
    cmp #$C0
    bcc tile
    jmp MARK_DIRTY
tile:
    lda #1
    sta a:$1C85
    lda a:$1C27
    and #$0F
    asl
    asl
    asl
    sta $04
    lda a:$1C26
    lsr
    lsr
    lsr
    lsr
    lsr
    ora $04
    tax
    lda a:$1D00,x
    ora #1
    sta a:$1D00,x
    lda a:$1C18
    and #1
    beq vertical_alias
    txa
    eor #$20
    bra alias
vertical_alias:
    txa
    eor #$40
alias:
    tax
    lda a:$1D00,x
    ora #1
    sta a:$1D00,x
    rts
