; A8 only, after the existing NMI-depth and bank-pair guards.
; Default expansion is byte-identical to the original NMI-only policy.
; Experimental $1CA2 is an IRQ-enable shadow (0 or $20), not a job counter.
.macro load_interrupt_enable
.ifdef RASTER_RECOVERY
    jsl $C10000+raster_rearm
.endif
    lda a:$1C20
    and #$80
.ifdef EXPERIMENTAL_RASTER
    ora a:$1CA2
.endif
.endmacro
