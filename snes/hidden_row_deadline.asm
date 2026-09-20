; Experimental wrapper around the unchanged, state-2-only direct-row helper.
; Entry native A16/X16, DB=0, DP=$1E00, NMI masked. Worker returns A8.
; Stop after a complete owned row (and its alias), never midway through DMA.
; Original maximum row budget still applies. Do not impose a new-frame wait.
.setcpu "65816"
.a16
.i16
.segment "CODE"
hidden_row_deadline:
    jsr HIDDEN_ROW_ENTRY
    .a8
    lda $213F
    lda $2137
    lda $213D
    pha
    lda $213D
    and #1
    bne @high
    pla
    cmp #240
    bcs @done                ; late VBlank precedes the coming active frame
    cmp #HIDDEN_ROW_DEADLINE
    bcc @done
    lda #1
    sta $1C6B                ; caller retires one budget unit, marks more work
@done:
    rts
@high:
    pla
    rts
hidden_row_deadline_end:
