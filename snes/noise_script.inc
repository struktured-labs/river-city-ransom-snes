; Diagnostic only: 60 frames each at rates 0..15, disabled, restarted,
; volume 1, volume 0. End phase holds. Same packet driver as other probes.
    rep #$20
    .a16
    lda FRAME
    .repeat 19, boundary
        cmp #60*(boundary+1)
        beq @noise_next
    .endrepeat
    sep #$20
    .a8
    bra @noise_done
@noise_next:
    sep #$20
    .a8
    inc PHASE
    lda PHASE
    cmp #16
    bcs @noise_special
    sta APU_PACKET+14
    bra @noise_done
@noise_special:
    cmp #17
    bcs @noise_restarted
    stz APU_PACKET+$15
    bra @noise_done
@noise_restarted:
    bne @noise_volume
    lda #6
    sta APU_PACKET+14
    lda #8
    sta APU_PACKET+$15
    sta APU_PACKET+$16
    bra @noise_done
@noise_volume:
    cmp #18
    bne @noise_zero
    lda #$31
    sta APU_PACKET+12
    bra @noise_done
@noise_zero:
    lda #$30
    sta APU_PACKET+12
@noise_done:
