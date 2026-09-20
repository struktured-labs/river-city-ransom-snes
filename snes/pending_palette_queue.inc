; Called only after $003E & $0A == $0A. Original C50B's fade budget is one
; WRITE command: a nonnegative head stops before any following read command.
; The write path cannot modify $003E or $0110..012F. Reject a read head and
; invalid nonempty ring pointers. No queue consumption or original RAM writes.
; A8/X16, DB=0. Clobbers A/X/Y/flags; outer preview saves those registers.
pending_palette_write_head:
    lda a:$06B6
    cmp a:$06B7
    beq @yes
    ; Only accelerate the initial color after black. Later generations keep
    ; the established publication path; changing their phase is not needed
    ; to reduce room-entry blackout and regressed the original room-2 fade.
.ifndef EXPERIMENTAL_PENDING_PALETTE_ALL_LEVELS
    lda a:$0692
    bne @no
.endif
    lda a:$06B6
    cmp #64
    bcs @no
    lda a:$06B7
    cmp #64
    bcs @no
    ; X8 avoids importing the caller's hidden accumulator high byte. INX
    ; avoids decimal-mode ADC; outer PHX/PHY restore both full-width indexes.
    sep #$10
    .i8
    ldx a:$06B6
    inx
    inx
    txa
    and #63
    tax
    lda a:$0545,x
    rep #$10
    .i16
    bmi @no
@yes:
    sec
    rts
@no:
    clc
    rts
