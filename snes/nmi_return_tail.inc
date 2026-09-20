; Original A/X/Y are on top of an emulation-mode P/PCL/PCH frame.
; No new WRAM flag: identify the retained camera continuation in that frame.
    pla
    tay
    pla
    tax
    pla
    pha
.ifdef EXPERIMENTAL_RETAINED_RETURN_EDGE
    ; Stack-relative addressing does not wrap at $01FF in emulation mode.
    ; An 8-bit X index explicitly follows the page-one hardware stack wrap.
    phx
    tsx
    inx
    inx
    inx
    inx
    lda a:$0100,x
    cmp #<camera_deferred_nmi_return
    bne @ordinary_stack
    inx
    lda a:$0100,x
    cmp #>camera_deferred_nmi_return
    bne @ordinary_stack
    plx
    bra @enable_return
@ordinary_stack:
    plx
.endif
@outside_vblank:
    lda $4212
    bmi @outside_vblank
@enable_return:
    dec a:$1C0A
    load_interrupt_enable
    sta $4200
    pla
    rti
