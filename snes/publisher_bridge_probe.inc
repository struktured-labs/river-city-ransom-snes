    ; Exercise the production emulation/native bridge with nondefault DB/D,
    ; known registers/flags and a bank-$00 caller, as on hardware NMI entry.
    rep #$20
    .a16
    lda #$1200
    tcd
    sep #$30
    .a8
    .i8
    sec
    xce
    lda #$7E
    pha
    plb
    ldx #$56
    ldy #$78
    lda #$34
    sec
    jsr publish_video
    sta f:$7E6000
    php
    pla
    sta f:$7E6001
    txa
    sta f:$7E6002
    tya
    sta f:$7E6003
    phb
    pla
    sta f:$7E6004
    phd
    pla
    sta f:$7E6005
    pla
    sta f:$7E6006
    tsx
    txa
    sta f:$7E6007
    phk
    pla
    sta f:$7E6008
    ; Restore the fixture's native readback ABI.
    clc
    xce
    lda #0
    rol
    sta f:$7E6009          ; Carry from XCE is the caller's restored E bit.
    rep #$30
    .a16
    .i16
    lda #$1E00
    tcd
    sep #$20
    .a8
    lda #0
    pha
    plb
