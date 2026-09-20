; Actual vectored hardware NMI, production native dispatch/queue/return tail.
; Video publisher and audio transport are controlled spies, not fidelity tests.
.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.include "early_audio_abi.inc"
.macro beam line
:
    lda $213F
    lda $2137
    lda $213D
    cmp #line
    bne :-
    lda $213D
    and #1
    bne :-
.endmacro
.macro input_abi
    ldx #$A6
    ldy #$59
    lda #$3C
    xba
    lda #FLAGS
    pha
    lda #$57
    plp
.endmacro
.macro record_abi target
    sta f:target
    php
    pla
    sta f:target+2
    xba
    sta f:target+1
    xba
    txa
    sta f:target+3
    tya
    sta f:target+4
    tdc
    sta f:target+5
    xba
    sta f:target+6
    xba
    phb
    pla
    sta f:target+7
    tsx
    txa
    sta f:target+8
.endmacro
.segment "NATIVE"
    .incbin "native-nmi.bin"
; The production JSR resolves here, at its unchanged original address.
    rts
.segment "EARLY"
early_audio_spy:
    php
    pha
    lda #1
    sta a:$1CFD
    lda a:$1C04
    sta a:$1CFE
    lda a:$1C05
    sta a:$1CFF
    jsr audio_spy
    pla
    plp
    rtl
.segment "CODE"
reset:
    sei
    clc
    xce
    rep #$38
    .a16
    lda #0
    tcd
    ldx #$1FFF
    txs
    sep #$20
    .a8
    pha
    plb
    stz $4200
    stz $420B
    stz $420C
    lda #$80
    sta $2100
    lda #1
    sta $420D
    lda #4
    sta $2133
    clear_wram_dma
    lda #<body
    sta a:$1C00
    lda #>body
    sta a:$1C01
    lda #BANK
    sta a:$1C02
    lda #$80
    sta a:$1C20
    lda #TASK
    sta a:$0100
    lda #DEPTH
    sta a:$1C0A
    lda #RETAINED
    sta a:$1CE0
    lda #MAIN
    sta a:$1CE1
    lda #1
    sta a:$1CEB
    lda #EARLY
    sta a:$1CFD
    lda #<OLD_ID
    sta a:$1C04
    lda #>OLD_ID
    sta a:$1C05
    lda #<(OLD_ID+MISMATCH)
    sta a:$1CFE
    lda #>(OLD_ID+MISMATCH)
    sta a:$1CFF
    lda #COUNTER
    sta a:$1CE4
    sta a:$1CE6
    lda #QUEUE_COUNTER
    sta a:$1B88
    sta a:$1B8A
    ; One previously published packet is represented independently of whether
    ; its production early-token is valid (negative admission cases vary it).
    sep #$10
    .i8
    jsr audio_spy
    rep #$20
    .a16
    lda #$1234
    tcd
    sep #$30
    .a8
    lda #$83
    pha
    plb
    sec
    xce
    ldx #STACK
    txs
    jml BANK*$10000+run
run:
    beam 40
    lda $4210
    beam 239
    lda #$80
    sta $4200
    input_abi
    wai
after_hardware:
    stz $4200
    record_abi $7E6000
    lda a:$1CE0
    sta f:$7E6040
    lda a:$1C04
    sta f:$7E6041
    lda a:$1C05
    sta f:$7E6042
    lda a:$1B90
    sta f:$7E6043
    lda a:$1B91
    sta f:$7E6044
    lda a:$1CE0
    beq finished
    ; Controlled camera completion recreates the exact E1 frame shape; the
    ; original body spy and production return tail then drain the newer job.
    stz a:$1CE0
    stz a:$1CE1
    inc a:$1CE4
    bne :+
    inc a:$1CE5
:
    lda #>after_camera
    pha
    lda #<after_camera
    pha
    lda #FLAGS
    pha
    inc a:$1C0A
    input_abi
    jmp body
after_camera:
    stz $4200
    record_abi $7E6020
finished:
    lda #1
    sta a:$1C60
alive:
    lda $4212
    bmi alive
:
    lda $4212
    bpl :-
    inc a:$1C62
    bne alive
    inc a:$1C63
    bra alive
body:
    pha
    txa
    pha
    tya
    pha
    ldx a:$1B90
    txa
    asl
    tax
    lda a:$1C04
    sta f:$7E6080,x
    lda a:$1C05
    sta f:$7E6081,x
    inc a:$1B90
    consume_early_audio body_done
    jsr audio_spy
body_done:
    jmp RETURN_TAIL
audio_spy:
    php
    pha
    phx
    ldx a:$1B91
    txa
    asl
    tax
    lda a:$1C04
    sta f:$7E6100,x
    lda a:$1C05
    sta f:$7E6101,x
    inc a:$1B91
    plx
    pla
    plp
    rts
.segment "RTI"
    rti
.segment "HEADER"
    .byte "RCR RETAINED ENTRY  "
    .byte " "
    .byte $31,$02,$0B,$00,$01,$33,$00
    .word 0,0
.segment "VECTORS"
    .word 0,0,0,0,0,NMI_ENTRY,0,0
    .word 0,0,0,0,0,NMI_ENTRY,reset,0
