; Initialize SRAM before an existing splash VBlank wait, not after SPC upload.
; No X/Y/DB/DP writes. Preserve status; original next_vblank supplies A/flags.
.setcpu "65816"
.a8
.i16
.segment "CODE"
    php
    .repeat 8, I
        lda f:magic+I
        sta f:$206000+I
    .endrepeat
    lda #0
    .repeat 8, I
        sta f:$206008+I
    .endrepeat
    lda #$20
    sta f:$20600C
    sta f:$20600E
    lda #$60
    sta f:$20600D
    plp
    jmp next_vblank
magic: .byte "RCRLOG01"
