; Diagnostic only, native A8/X16/DB=0 at the audio bridge.
; SRAM must be preseeded. No game startup initializer or game-state write.
.setcpu "65816"
.a8
.i16
.segment "CODE"
.export camera_log_frame, camera_log_sample, camera_log_end

camera_log_frame:
    jsr spc_frame
    php
    rep #$20
    .a16
    pha                         ; preserve hidden B and original timeout carry
    phx
    phy
    sep #$20
    .a8
    phb
    ; Preserve the actual sender status before gate CMPs change carry.
    bcc :+
    lda #1
    bra :++
:   lda #0
:   pha
    ; Capture only fully visible active gameplay; pause freezes the log.
    lda a:$0100
    cmp #$C0
    bne skip
    lda a:$0692
    cmp #4
    bne skip
    lda a:$1CA0
    bne skip
    lda a:$1C21
    and #8
    beq skip
    lda a:$003E
    and #$82
    bne skip
    lda a:$0107
    bmi skip
    lda a:$003F
    and #$20
    bne skip
    ; Fail closed if cartridge SRAM was not initialized by the host.
    rep #$20
    .a16
    lda f:$206000
    cmp #$4352                  ; RC
    bne skip16
    lda f:$206002
    cmp #$4352                  ; RC
    bne skip16
    lda f:$206004
    cmp #$4D41                  ; AM
    bne skip16
    lda f:$206006
    cmp #$3130                  ; 01
    bne skip16
    sep #$20
    .a8
    bra record
skip16:
    sep #$20
    .a8
skip:
    pla
    jmp restore
record:
    lda f:$20600E
    pha
    plb
    rep #$20
    .a16
    lda f:$20600C
    tax
    sep #$20
    .a8
    pla
    sta a:6,x
    lda #0
    sta a:31,x
    .repeat 4,I
        lda f:$206008+I
        sta a:I,x
    .endrepeat
camera_log_sample:
    lda f:$001C04
    sta a:4,x
    lda f:$001C05
    sta a:5,x
    ; Field order is shared with tools/camera_state_log.py.
    .repeat 23,I
        .scope
        .if I = 0
            ADDRESS = $00DC
        .elseif I = 1
            ADDRESS = $00DD
        .elseif I = 2
            ADDRESS = $00F6
        .elseif I = 3
            ADDRESS = $003D
        .elseif I = 4
            ADDRESS = $1C94
        .elseif I = 5
            ADDRESS = $1C95
        .elseif I = 6
            ADDRESS = $1C97
        .elseif I = 7
            ADDRESS = $1C98
        .elseif I = 8
            ADDRESS = $010B
        .elseif I = 9
            ADDRESS = $1CE0
        .elseif I = 10
            ADDRESS = $1CE1
        .elseif I = 11
            ADDRESS = $1CEB
        .elseif I = 12
            ADDRESS = $1CE4
        .elseif I = 13
            ADDRESS = $1CE5
        .elseif I = 14
            ADDRESS = $1CE6
        .elseif I = 15
            ADDRESS = $1CE7
        .elseif I = 16
            ADDRESS = $0042
        .elseif I = 17
            ADDRESS = $003F
        .elseif I = 18
            ADDRESS = $003E
        .elseif I = 19
            ADDRESS = $4212
        .elseif I = 20
            ADDRESS = $1C04
        .elseif I = 21
            ADDRESS = $1C05
        .else
            ADDRESS = $0107
        .endif
        lda f:ADDRESS
        sta a:7+I,x
        .endscope
    .endrepeat
    lda #0
    .repeat 30,I
        eor a:I,x
    .endrepeat
    sta a:30,x
    lda #$A5
    sta a:31,x
    rep #$20
    .a16
    txa
    clc
    adc #32
    cmp #$8000
    bne pointer_ready
    sep #$20
    .a8
    lda f:$20600E
    inc
    cmp #$30
    bne :+
    lda #$20
:   sta f:$20600E
    cmp #$20
    beq first_bank
    rep #$20
    .a16
    lda #$6000
    bra pointer_ready
first_bank:
    rep #$20
    .a16
    lda #$6020
pointer_ready:
    sta f:$20600C
    lda f:$206008
    inc
    sta f:$206008
    bne :+
    lda f:$20600A
    inc
    sta f:$20600A
:   sep #$20
    .a8
restore:
    plb
    rep #$20
    .a16
    ply
    plx
    pla
    plp
    .a8
    rts
camera_log_end:
