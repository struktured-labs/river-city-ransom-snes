; Enter A16/X16 after a completed row DMA, in bank 00/C0 with DB=0.
; Account for every transferred row first, then stop searching if the
; existing row-room deadline has arrived. Never consume another queued row.
.setcpu "65816"
.a16
.i16
.segment "CODE"
.export postdma_deadline
postdma_deadline:
    jsr ADVANCE_ROWS
    sep #$20
    jsr ROW_ROOM
    rep #$20
    bcs continue_scan
    ; Same cursor increment/wrap as the original next_row prefix.
    inx
    cpx #128
    bcc finish
    ldx #0
finish:
    jmp ROW_FINISH
continue_scan:
    jmp NEXT_ROW
