; Specialize the write dispatcher only for PPUCTRL, OAMADDR, PPUSCROLL and
; PPUADDR. Caller mailbox/interrupt ownership and the legacy fallback remain.
; E=1/A8/X8. Match legacy hidden B=$1B as well as A/P/X/Y/D/DB/SP.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export ppu_register_fast
ppu_register_fast:
    php
    pha
    stz $4200
    lda a:$1B21
    cmp #$20
    bne fallback
    lda a:$1B20
    and #7
    beq control
    cmp #3
    beq oam_address
    cmp #5
    beq scroll
    cmp #6
    beq address
fallback:
    pla
    plp
    ; Replay overwritten PHP/PHA/PHX and join the original PHY/PHD prologue.
    php
    pha
    phx
    jmp OLD_BODY
control:
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
oam_address:
    lda a:$1B22
    sta a:$1C23
    bra done
scroll:
    phx
    ldx a:$1C25
    lda a:$1B22
    sta a:$1C28,x
    txa
    eor #1
    sta a:$1C25
    plx
    bra done
address:
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
    pla
    plp
    rtl
