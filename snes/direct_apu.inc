; Direct entry for the checked self-modifying STA $400x helper. E=1/A8/X8.
; Preserve the original caller once, not once in the stub and again in the
; generic dispatcher. The generated stub checks $07F9/A before entering;
; all other addresses tail through the unchanged original generic stub.
direct_dynamic_apu:
    stz $4200
    php
    pha
    sta a:$1B22
    phx
    phy
    lda a:$07F9
    sta a:$1B20
    tax
    lda #$40
    sta a:$1B21
    cpx #$15
    bne @channel
    lda a:$1B22
    sta a:$0A00,x
    and a:$1CA1
    sta a:$1CA1
    bra @enable
@channel:
    lda a:$1B22
    sta a:$0A00,x
    txa
    and #3
    cmp #3
    bne @flags
    lda f:$C10000+direct_apu_flags,x
    and #$0F
    and a:$0A15
    ora a:$1CA1
    sta a:$1CA1
@flags:
.ifdef EXPERIMENTAL_SWEEP_EVENTS
    jsr sweep_track_write
.endif
    lda f:$C10000+direct_apu_flags,x
    ora a:$0A16
    sta a:$0A16
@enable:
    lda a:$1C0A
    ora a:$1C83
    bne @return
    load_interrupt_enable
    beq @return
    sta $4200
@return:
    ply
    plx
    pla
    plp
    rtl
direct_apu_flags:
    .byte $00,$00,$40,$41,$00,$00,$80,$82
    .byte $00,$00,$00,$04,$00,$00,$00,$08
