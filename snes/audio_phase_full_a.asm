; Preserve the hidden accumulator byte across the real native audio bridge.
;3665 retained only A.low; the actual IRQ trace proves A.high was damaged.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export arm_full_a, drain_full_a, recover_full_a, irq_full_a
.macro outer_save
    php
    xba
    pha
    xba
.endmacro
.macro outer_restore
    ; Keep the callee's result A.low, restore the caller's A.high.
    pha
    pla
    xba
    pla
    xba
    plp
.endmacro
arm_full_a:
    outer_save
    jsl $C17800
    outer_restore
    rtl
drain_full_a:
    outer_save
    jsl $C17858
    outer_restore
    rtl
recover_full_a:
    outer_save
    jsl $C1789A
    outer_restore
    ; The displaced LDA/AND policy updates N/Z, not caller C/V/D/I.
    ora #0
    rtl
irq_full_a:
    php
    pha
    xba
    pha
    xba
    phx
    phy
    phd
    phb
    cld
    pea 0
    pld
    stz $4200
    lda $4211
    jsr $7885
    lda #$D8
    sta $1CA4
    lda #$F1
    sta $1CA5
    lda $1C02
    sta $1CA6
    lda $1C20
    and #$80
    sta $4200
    plb
    pld
    ply
    plx
    pla
    xba
    pla
    plp
    jml [$1CA4]
