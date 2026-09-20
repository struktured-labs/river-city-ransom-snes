; Experimental packet $14 metadata, distinct from legacy packet $16 flags.
; A8/X8, X=just-written register. Called only with hardware NMI masked.
; Clobbers A/flags; preserves X/Y/DP/DB. No event inference from value changes.
sweep_track_write:
    cpx #$17
    beq @frame
    lda f:$C10000+sweep_event_bits,x
    beq @done                  ; most writes change volume, not sweep state
    ora a:$0A14
    sta a:$0A14
@done:
    rts
@frame:
    lda a:$0A14
    and #$3F
    ora #$40
    sta a:$0A14
    lda a:$0A17
    and #$80
    ora a:$0A14
    sta a:$0A14
    rts
sweep_event_bits:
    .byte $00,$01,$04,$08,$00,$02,$10,$20
    .byte $00,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$00
