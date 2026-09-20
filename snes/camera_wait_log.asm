; Offline diagnostic: only spend recorder work inside the original tick wait.
; Entry is a JMP replacing F2C9's first LDA, not an extra frame around FAB8.
.setcpu "65816"
.a8
.i8
.segment "CODE"
camera_wait_log:
    lda a:$010B
    cmp #2
    bcs finished
    php
    pha
    phx
    phy
    ; Reject interrupt/coroutine contexts before changing interrupt policy.
    lda a:$1C0A
    ora a:$1C83
    bne restore
    lda a:$1CE0
    bne restore
    ; Stay in emulation mode with the original DB until admission completes.
    lda a:$213F
    lda a:$2137
    lda a:$213D
    tax
    lda a:$213D
    and #1
    bne restore
    txa
    cmp #194
    bcs restore
    stz a:$4200
    jsl $C0E400
    ; Current supported cartridge has no raster IRQ or auto joypad policy.
    lda a:$1C20
    and #$80
    sta a:$4200
restore:
    ply
    plx
    pla
    plp
wait_tick:
    lda a:$010B
    cmp #2
    bcc wait_tick
finished:
    jmp $F2D0
