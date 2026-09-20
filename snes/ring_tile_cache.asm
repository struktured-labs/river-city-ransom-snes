; Retain the prior stride32-only admission and pointer cache. Specialize only
; its internal dirty marker; ring caller saves X/P, so the marker need not.
MARK_DIRTY = ring_tile_mark
.include "ring_stride_cache.asm"

ring_tile_mark:
    lda a:$1C27
    and #3
    cmp #3
    bne tile
    lda a:$1C26
    cmp #$C0
    bcc tile
    jmp ORIGINAL_MARK_DIRTY
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
