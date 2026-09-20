; Caller owns the masked camera critical section, A8. X/Y/DP/DB untouched.
; Both street HDMA entries must retain one generation throughout lines32..193.
; Default: before line30. Optional line30 experiment retains a full remaining
; scanline for the four stores before line32; it is not promoted to Rival.
; At/after194 the street is finished; high vertical bit means lines256..261.
camera_publish_safe:
    lda $213F
    lda $2137
    lda $213D
    pha
    lda $213D
    and #1
    bne @high
    pla
.ifdef EXPERIMENTAL_CAMERA_LINE30
    cmp #31
.else
    cmp #30
.endif
    bcc @publish
    cmp #194
    bcc @defer
    bra @publish
@high:
    pla
@publish:
    lda $F6
    sta a:$1C94
    sta a:$1C97
    lda $3D
    and #1
    sta a:$1C95
    sta a:$1C98
    sec
    rts
@defer:
    ; F6/3D still hold the complete new camera. The next bounded VBlank
    ; publisher rebuilds both entries from those values; no game tick waits.
    clc
    rts
