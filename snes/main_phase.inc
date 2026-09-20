; Optional stable-game start phase, E=1/A8/X8. NMI remains untouched/enabled.
; Wait only inside the current early active frame, never for a new frame.
; Preserve incoming registers/flags before the original iteration-start hook.
gameplay_phase_start:
    php
    pha
    jsr gameplay_phase_wait
    pla
    plp
    jmp gameplay_iteration_start

gameplay_phase_wait:
    lda a:$0100
    and #$C0
    cmp #$C0
    bne @done
    lda a:$0107
    bmi @done
    lda a:$003F
    and #$20
    bne @done
    lda a:$003E
    and #$82
    bne @done
    lda a:$0692
    cmp #4
    bne @done
    lda a:$1CA0
    ora a:$1C0A
    ora a:$1C83
    ora a:$1CE0
    ora a:$1CE1
    bne @done
    lda a:$1CEB
    beq @done
    lda a:$1C20
    bpl @done
@beam:
    lda $213F
    lda $2137
    lda $213D
    pha
    lda $213D
    and #1
    bne @high
    pla
    cmp #MAIN_PHASE_LINE
    bcc @beam
@done:
    rts
@high:
    pla
    rts
