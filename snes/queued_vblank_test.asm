; Actual MMIO collection, full production helper/return tail, controlled body.
.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
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
.macro collect
    input_abi
.if READ_KIND = 1
    jsl $C10000+READ_LONG
.elseif READ_KIND = 2
    jsr READ_SHORT
.else
    jsr COLLECT
.endif
    record_abi $7E6000
    ; A separate repeated probe checks acknowledgment, not just a software
    ; "already seen this frame" latch.
    jsr COLLECT
.endmacro
.segment "NATIVE"
native_nmi:
    stz $4200
    pha
    lda $4210
native_after_ack:
    inc a:$1C0A
    inc a:$1C04
    bne :+
    inc a:$1C05
:
    pla
    jml BANK*$10000+body
.assert native_nmi = NMI_ENTRY, error, "Wrong hardware entry"
.assert native_after_ack = NMI_ENTRY+7, error, "Wrong queued entry"
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
    lda #DEPTH
    sta a:$1C0A
    lda #TASK
    sta a:$0100
    lda #CONTROL
    sta a:$1C20
    lda #PENDING
    sta a:$1B87
    lda #COUNTER
    sta a:$1B88
    sta a:$1B8A
    lda #1
    sta a:$1C04
    lda #$BC
    sta a:$05EB
    rep #$20
    .a16
    lda #$1234
    tcd
    sep #$30
    .a8
    .i8
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
.if EVENTS = 0
    collect
.else
    .repeat EVENTS
        beam 241
        .if ACKNOWLEDGED
            lda $4210
        .endif
        collect
        beam 0
    .endrepeat
.endif
    lda a:$1B87
    sta f:$7E6020
    lda a:$1C04
    sta f:$7E6021
    lda a:$1B88
    sta f:$7E6022
    lda a:$1B89
    sta f:$7E6023
.if PENDING = 255
    jmp finished
.endif
.if TAIL_PENDING
    beam 241
.endif
    ; Set up the already-running old interrupt with a genuine E1 RTI frame.
    ; Only its task body is controlled; production collector/tail-chain execute.
    lda #1
    sta a:$1C0A
    lda #$C0
    sta a:$0100
    lda #$80
    sta a:$1C20
    lda #>after
    pha
    lda #<after
    pha
    lda #FLAGS
    pha
    lda #$3C
    xba
    lda #$57
    ldx #$A6
    ldy #$59
    jmp body
body:
    pha
    txa
    pha
    tya
    pha
    ldx a:$1B8E
    lda a:$1C04
    sta a:$1B90,x
    inc a:$1B8E
    jmp RETURN_TAIL
after:
    stz $4200
    record_abi $7E6010
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
.segment "HEADER"
    .byte "RCR QUEUED VBLANK    "
    .byte $31,$02,$0B,$00,$01,$33,$00
    .word 0,0
.segment "VECTORS"
    .word 0,0,0,0,0,native_nmi,0,0
    .word 0,0,0,0,0,native_nmi,reset,0
