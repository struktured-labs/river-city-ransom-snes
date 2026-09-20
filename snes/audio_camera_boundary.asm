; Experimental: claim near-due audio before camera/retained-NMI critical work.
; Same-bank JMP replaces camera entry STZ4200. Preserve the original full state.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export entry
entry:
    stz $4200
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
    lda $1CA3
    beq restore
    lda $1C0A
    ora $1C83
    bne restore
    lda $1C20
    bpl restore
    lda $213F
    lda $2137
    lda $213D
    tax
    lda $213D
    and #1
    bne restore
    cpx #60
    bcc restore
    cpx #240
    bcs restore
    ; Existing service atomically claims pending; its depth guard protects
    ; mapper/APU adapters. Do not manufacture a completed-audio token.
    jsr $7885
restore:
    plb
    pld
    ply
    plx
    pla
    xba
    pla
    plp
    jmp $325F
