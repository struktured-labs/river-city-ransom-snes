; Original C2C3..C2E2, E=1/A8/X8, original DP/DB. No NMI policy change.
; Common column: 20 pointer-table reads, ring writes and per-row $21 progress.
; Other entry counts retain the original loop, including 8-bit count wrap.
native_column_fetch:
    lda $21
    cmp #8
    beq @column
@generic:
    ldy $21
    lda ($1A),y
    sta $1E
    iny
    lda ($1A),y
    sta $1F
    ldy $20
    lda ($1E),y
    sta $0545,x
    inx
    txa
    and #$3F
    tax
    inc $21
    inc $21
    lda $21
    cmp #$30
    bcc @generic
    jmp $C2E3
@column:
    .repeat 20, row
        ldy #8+row*2
        lda ($1A),y
        sta $1E
        iny
        lda ($1A),y
        sta $1F
        ldy $20
        lda ($1E),y
        sta $0545,x
        inx
        txa
        and #$3F
        tax
        ; Publish the completed-row count each iteration, not only at exit.
        ; The original two INCs expose an intermediate odd count; this STA
        ; does not. No claim of cycle-by-cycle interrupt-state equivalence.
        lda #10+row*2
        sta $21
    .endrepeat
    cmp #$30
    jmp $C2E3
