.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
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
    clear_wram_dma
    lda #4
    sta $2133
    lda #PENDING
    sta a:$1B80
    rep #$20
    .a16
    lda #$1234
    tcd
    sep #$30
    .a8
    .i8
    lda #$82
    pha
    plb
    sec
    xce
    ldx #STACK
    txs
blank:
    lda $4212
    bpl blank
visible:
    lda $4212
    bmi visible
target:
    lda $213F
    lda $2137
    lda $213D
    cmp #<TARGET_LINE
    bne target
    lda $213D
    and #1
    cmp #>TARGET_LINE
    bne target
    lda #>(CAMERA_RETURN+ORDINARY)
    pha
    lda #<(CAMERA_RETURN+ORDINARY)
    pha
    lda #$35
    pha
    lda #$40
    pha
    lda #$56
    pha
    lda #$78
    pha
    ldx #$56
    ldy #$78
    jml BANK*$10000+call_guard
call_guard:
    jsr GUARD_ENTRY
    txa
    sta f:$7E6000
    tya
    sta f:$7E6001
    tsx
    txa
    sta f:$7E6002
    ; PHD is a native-width stack operation even in E=1; do not make the
    ; observer itself spill below page one when testing SP=$0100.
    tdc
    sta f:$7E6003
    xba
    sta f:$7E6004
    xba
    phb
    pla
    sta f:$7E6005
    .repeat 6,I
        pla
        sta f:$7E6006+I
    .endrepeat
    tsx
    txa
    sta f:$7E600C
    lda a:$1B80
    sta f:$7E600D
    lda #1
    sta a:$1C60
alive:
    lda $4212
    bmi alive
wait_blank:
    lda $4212
    bpl wait_blank
    inc a:$1C62
    bne alive
    inc a:$1C63
    bra alive
.segment "FALLBACK"
    lda #1
    sta f:$7E600E
    stz a:$1B80
    rts
.segment "PREPARE"
    lda #2
    sta f:$7E600E
    stz a:$1B80
    rts
.segment "GUARD"
    .incbin "retained-guard.bin"
.segment "HEADER"
    .byte "RCR RETAINED GUARD   "
    .byte $31,$00,$0B,$00,$01,$00,$00
    .word $FFFF,$0000
.segment "VECTORS"
    .word 0,0,reset,reset,reset,reset,reset,reset
    .word 0,0,reset,0,reset,reset,reset,reset
