; A8/X16, DB=0, DP=$1E00. Native publisher runs in bank C0 or 00.
; Check the existing row admission deadline even when searching empty slots.
; Deferred rows keep their flags, cursors and staging; final batch keeps its
; independent final_room check. Forced-blank admission is unchanged.
.setcpu "65816"
.a8
.i16
.segment "CODE"
.export bounded_row_scan
bounded_row_scan:
    sep #$20
    jsr ROW_ROOM
    bcc finish
    cpx #121
    jmp ROW_CONTINUE
finish:
    jmp ROW_FINISH
