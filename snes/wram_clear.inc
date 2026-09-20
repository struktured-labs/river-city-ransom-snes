; Inline reset-only clear. E=0, A8/X16, DB=0; interrupts and HDMA disabled.
; No return address may live in WRAM: the operation clears the stack too.
.macro clear_wram_dma
    .local zero_byte, finished, transfer
    stz $2181
    stz $2182
    stz $2183
    lda #8                 ; fixed A-bus source, mode 0, CPU -> WMDATA
    sta $4300
    lda #$80
    sta $4301
    ldx #zero_byte
    stx $4302
    lda #$C0
    sta $4304
    ldy #4                 ; each 32KiB transfer is shorter than one frame
transfer:
    ldx #$8000
    stx $4305
    lda #1
    sta $420B
    dey
    bne transfer           ; WMDATA increments across both physical WRAM banks
    lda #0
    ldx #0
    bra finished
zero_byte:
    .byte 0
finished:
.endmacro
