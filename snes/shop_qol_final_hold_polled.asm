; Final shop result hold, v2: poll pads while yielding instead of relying on
; the suspended outer shop loop. F0/F1 are HELD; EE/EF are rising edges.
; Failed v1 remains immutable as a negative control (could not dismiss).
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export shop_qol_final_hold
shop_qol_final_hold:
    lda $2A
    pha
    lda $2B
    pha
    jsr $9960
    ldy #1
    lda ($2A),y
    and #$80
    dey
    ora ($2A),y
    tax
    pla
    sta $2B
    pla
    sta $2A
    txa
    beq finish
release:
    jsr frame
    jsr buttons
    bne release
press:
    jsr frame
    jsr buttons
    beq press
finish:
    jmp $921F
buttons:
    lda a:$0687
    and #1
    tax
    lda a:$00F0,x
    and #$C0
    rts
frame:
    jsr $FC60
    jsr $FC4D
    jsr $E2C0
    jsr $FADA
    jsr $FA54
    jsr $FD18                 ; original pad poll and edge/held update
    rts
