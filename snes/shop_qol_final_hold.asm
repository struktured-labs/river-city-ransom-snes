; Opt-in final consumption-result hold, original US shop state machine.
; E=1, A8/X8; bank-local absolute calls remain the original game's calls.
; No new RAM state, equipment/stat writes, text, tiles or sound commands.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export shop_qol_final_hold
shop_qol_final_hold:
    ; A statless item must never wait for a result that was not displayed.
    lda $2A
    pha
    lda $2B
    pha
    jsr $9960                  ; original item stat-mask pointer
    ldy #1
    lda ($2A),y
    and #$80                   ; stamina mask; lower bits are not stat flags
    dey
    ora ($2A),y                ; combat/Will flags
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
    bne release                ; an already-held accept cannot dismiss
press:
    jsr frame
    jsr buttons
    beq press                  ; require a new A/B press by consuming player
finish:
    jmp $921F                  ; retain original completion housekeeping
buttons:
    lda a:$0687
    and #1
    tax
    lda a:$00EE,x              ; original routed P1/P2 held controller state
    and #$C0
    rts
frame:
    jsr $FC60                  ; original cooperative frame yield, sound keeps running
    jsr $FC4D
    jsr $E2C0
    jsr $FADA
    jsr $FA54
    rts
