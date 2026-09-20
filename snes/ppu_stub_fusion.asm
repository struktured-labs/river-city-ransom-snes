; Private callees ONLY for pinned PPU write stubs. The caller has already
; masked NMI, filled the mailbox and saved original A/P. It immediately does
; PLA/PLP after our RTL. X/Y/D/DB must survive; B must become the legacy$1B.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export fused_control, fused_oam_address, fused_scroll, fused_address
fused_control:
    lda a:$1B22
    eor a:$1C20
    and #$18
    beq :+
    lda #1
    sta a:$1CBB
:
    lda a:$1B22
    sta a:$1C20
    bra done
fused_oam_address:
    lda a:$1B22
    sta a:$1C23
    bra done
fused_scroll:
    phx
    ldx a:$1C25
    lda a:$1B22
    sta a:$1C28,x
    txa
    eor #1
    sta a:$1C25
    plx
    bra done
fused_address:
    lda a:$1C25
    bne low_address
    lda a:$1B22
    and #$3F
    sta a:$1C27
    lda #1
    sta a:$1C25
    bra done
low_address:
    lda a:$1B22
    sta a:$1C26
    stz a:$1C25
done:
    lda #$1B
    xba
    rtl
