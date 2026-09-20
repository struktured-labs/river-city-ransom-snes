; Equivalent DFE2 entry for E=1/A8/X8. No direct-page scratch or mode changes.
; Preserve the original nonterminating path for malformed, unaligned counts.
.setcpu "65816"
.a8
.i8
.segment "CODE"
hide_tail:
    ldx a:$052D
    bne @nonzero
    jmp $DFF7
@nonzero:
    txa
    and #3
    beq @aligned
    lda #$F0
    jmp $DFE9
@aligned:
    lda #$F0
    jmp (dispatch,x)
dispatch:
    .repeat 64, slot
        .if slot < 2
            .word finish, finish
        .else
            .word stores+(63-slot)*3, finish
        .endif
    .endrepeat
stores:
    .repeat 62, slot
        sta a:$0200+(63-slot)*4
    .endrepeat
finish:
    ldx #4
    cpx #4                  ; original final N/Z/C, other flags untouched
    jmp $DFF7
