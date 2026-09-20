.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.export nmi, native_fault
RECORD_BASE = RECORD_BANK*$10000+RECORD_POINTER
.segment "CODE"
reset:
    jml SOURCE_BANK*$10000+entry
entry:
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
    lda #1
    sta $420D
    lda #$80
    sta $2100
    lda #4
    sta $2133
    clear_wram_dma
    rep #$20
    .a16
    lda #$4352
    sta f:$206000
    sta f:$206002
    lda #$4D41
    sta f:$206004
    lda #$3130
    sta f:$206006
    lda #(RECORD_COUNT & $FFFF)
    sta f:$206008
    lda #((RECORD_COUNT >> 16) & $FFFF)
    sta f:$20600A
    lda #RECORD_POINTER
    sta f:$20600C
    sep #$20
    .a8
    lda #RECORD_BANK
    sta f:$20600E
    lda #$CC
    ldx #31
@clear_record:
    sta f:RECORD_BASE,x
    dex
    bpl @clear_record
    lda #$C0
    sta a:$0100
    lda #4
    sta a:$0692
    sta a:$003E
    lda #8
    sta a:$1C21
    lda #$80
    sta a:$1C20
    lda #START_TICK
    sta a:$010B
    lda #CONTEXT_NMI
    sta a:$1C0A
    lda #CONTEXT_COROUTINE
    sta a:$1C83
    lda #CONTEXT_PENDING
    sta a:$1CE0
    lda #$34
    sta a:$00DC
    sta a:$00F6
    sta a:$1C94
    sta a:$1C97
    lda #1
    sta a:$00DD
    sta a:$003D
    sta a:$1C95
    sta a:$1C98
.if ENABLE_HDMA
    ; Production channel-1 mode-2 horizontal-scroll schedule. Both repeated
    ; street entries use the same shadow fields sampled by the recorder.
    lda #32
    sta a:$1C90
    stz a:$1C91
    stz a:$1C92
    lda #127
    sta a:$1C93
    lda #35
    sta a:$1C96
    lda #45
    sta a:$1C99
    stz a:$1C9A
    stz a:$1C9B
    stz a:$1C9C
    lda #2
    sta a:$4310
    lda #$0D
    sta a:$4311
    ldx #$1C90
    stx a:$4312
    lda #$7E
    sta a:$4314
    lda #2
    sta a:$420C
.endif
    rep #$20
    .a16
    lda #DIRECT_PAGE
    tcd
    ldx #$01FF
    txs
    sep #$30
    .a8
    .i8
    lda #DATA_BANK
    pha
    plb
    sec
    xce
@blank:
    lda a:$4212
    bpl @blank
@visible:
    lda a:$4212
    bmi @visible
@target:
    lda a:$213F
    lda a:$2137
    lda a:$213D
    cmp #<TARGET_LINE
    bne @target
    lda a:$213D
    and #1
    cmp #>TARGET_LINE
    bne @target
    lda a:$4210
    lda #$80
    sta a:$4200
    .repeat DELAY_NOPS
        nop
    .endrepeat
    lda #$A5
    xba
    lda #$56
    ldx #$56
    ldy #$78
    ; Exercise decimal/overflow preservation; final CMP defines N/Z/C.
    lda #$4C
    pha
    plp
    jmp $7B00

.segment "FINISH"
finished:
    sta f:$7E6000
    php
    pla
    sta f:$7E6001
    txa
    sta f:$7E6002
    tya
    sta f:$7E6003
    xba
    sta f:$7E6004
    xba
    tsx
    txa
    sta f:$7E6005
    phd
    pla
    sta f:$7E6006
    pla
    sta f:$7E6007
    phb
    pla
    sta f:$7E6008
    stz a:$4200
    clc
    xce
    lda #0
    rol a
    sta f:$7E6009
    cld
    lda a:$213F
    lda a:$2137
    lda a:$213D
    sta f:$7E6010
    lda a:$213D
    and #1
    sta f:$7E6011
    ldx #15
@header:
    lda f:$206000,x
    sta f:$7E6020,x
    dex
    bpl @header
    ldx #31
@record:
    lda f:RECORD_BASE,x
    sta f:$7E6040,x
    dex
    bpl @record
    lda #1
    sta a:$1C60
@alive:
    lda a:$4212
    bmi @alive
@next:
    lda a:$4212
    bpl @next
    inc a:$1C62
    bne @alive
    inc a:$1C63
    bra @alive

.segment "CODE"
nmi:
    ; Emulation RTI cannot recover PB: restore the interrupted replica first,
    ; just as the production adapter does before resuming low-half ROM code.
    jml SOURCE_BANK*$10000+nmi_body
nmi_body:
    pha
    lda a:$4210
    inc a:$010B
    inc a:$1C04
    bne :+
    inc a:$1C05
:
    lda a:$213F
    lda a:$2137
    lda a:$213D
    sta f:$7E600C
    lda a:$213D
    and #1
    sta f:$7E600D
    inc a:$1BB0
    pla
    rti
native_fault:
    sep #$20
    lda #$FF
    sta f:$7E1C60
    stp
irq:
    rti
.segment "WAIT"
    .incbin "wait.bin"
.segment "LOGGER"
    .incbin "logger.bin"
.segment "IDLE"
    .incbin "idle.bin"
.segment "HEADER"
    .byte "RCR CAMERA WAIT TEST "
    .byte $31,$02,$0B,$07,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,native_fault,native_fault,native_fault,native_fault,0,native_fault
    .word 0,0,irq,0,irq,nmi,reset,irq
