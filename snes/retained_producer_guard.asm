; Offline experiment. E=1/A8/X8, DB mirrors WRAM, NMI masked by nmi_rti_return.
; Both entries are called directly from the original NMI-return body while
; saved A/X/Y and the emulation interrupt frame are still on the stack.
.setcpu "65816"
.a8
.i8
.export guarded_fallback, guarded_prepare, should_defer
.segment "CODE"
guarded_fallback:
    jsr should_defer
    bcs deferred
    jmp FALLBACK
guarded_prepare:
    jsr should_defer
    bcs deferred
    jmp PREPARE
deferred:
    rts

should_defer:
    ; Only defer already-owned work. The ordinary next interrupt exit retains
    ; fallback responsibility; no dirty flag, row, or counter is consumed here.
    lda a:$1B80
    beq ordinary
    phx
    tsx
    ; Two JSRs plus saved X are above the entry stack. Saved RTI low/high are
    ; entry SP+5/+6, hence current SP+10/+11. Explicit X8 wraps within page one.
    .repeat 10
        inx
    .endrepeat
    lda a:$0100,x
    cmp #<CAMERA_RETURN
    bne not_retained
    inx
    lda a:$0100,x
    cmp #>CAMERA_RETURN
    bne not_retained
    plx
    lda $213F
    lda $2137
    lda $213D
    pha
    lda $213D
    and #1
    bne late_high
    pla
    cmp #194
    bcc ordinary
    sec
    rts
late_high:
    pla
    sec
    rts
not_retained:
    plx
ordinary:
    clc
    rts
