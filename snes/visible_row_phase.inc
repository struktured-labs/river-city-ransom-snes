; A8/X16, DB=0. Read original state only; preserve X/Y/DP/stack.
; Only stable, unpaused gameplay participates. A=0 defers rows alone,
; A=4 prepares their two-tick allowance, A=2 retains the ordinary budget.
; Palette, sprites, CHR and audio still run every original NMI.
visible_row_phase_budget:
    .a8
    lda a:$0100
    and #$C0
    cmp #$C0
    bne @ordinary
    lda a:$0107
    bmi @ordinary
    lda a:$003F
    and #$20
    bne @ordinary
    lda a:$003E
    and #$82
    bne @ordinary
    lda a:$0692
    cmp #4
    bne @ordinary
    lda a:$1CA0
    bne @ordinary
    lda a:$010B
    cmp #1
    beq @first
    cmp #2
    bne @ordinary
    lda #0
    rts
@first:
    lda #4
    rts
@ordinary:
    lda #2
    rts
