; Original bank-5 $8735: shadow one sound register, suppress stolen music
; channels, then write the selected NES register. E=1/A8/X8, ordinary RTS ABI.
native_sound_commit:
    sta a:$07D6,y
    cpx #4
    bcs @effect
    lda a:$074C,x
    beq @music
    rts
@music:
    sty a:$07F9
    bra @write
@effect:
    tya
    and #$0F
    sta a:$07F9
@write:
    lda a:$07D6,y
    stz $4200
    ; Save the ORIGINAL result. The original CPX determines carry and its
    ; final LDA determines N/Z. Reconstruct those after restoring X/A; this
    ; body never changes V/D/I. Y is never changed. Keep A on the stack so
    ; an NMI after re-enable cannot change our return value via sound RAM.
    pha
    phx
    ldx a:$07F9
    lda a:$07FA
    cmp #$40
    bne @fallback
    cpx #$10
    bcc @channel
    cpx #$15
    bne @fallback
    lda a:$07D6,y
    sta a:$0A00,x
    and a:$1CA1
    sta a:$1CA1
    bra @enable
@channel:
    lda a:$07D6,y
    sta a:$0A00,x
.ifdef EXPERIMENTAL_SWEEP_EVENTS
    jsr sweep_track_write
.endif
    lda f:$C10000+direct_apu_flags,x
    beq @enable
    ora a:$0A16
    sta a:$0A16
    txa
    and #3
    cmp #3
    bne @enable
    lda f:$C10000+direct_apu_flags,x
    and #$0F
    and a:$0A15
    ora a:$1CA1
    sta a:$1CA1
    bra @enable
@fallback:
    ; Preserve all other virtual addresses, including DMA/controllers. The
    ; dispatcher may restore a different PB/DB for mapper writes; its JSL
    ; return then lands in this same replicated continuation in that bank.
    sta a:$1B21
    stx a:$1B20
    lda a:$07D6,y
    sta a:$1B22
    jsl $C10000+dispatch_write
@enable:
    lda a:$1C0A
    bne @return
    lda a:$1C83
    bne @return
    load_interrupt_enable
    beq @return
    sta $4200
@return:
    plx
    cpx #4
    pla
    rts
