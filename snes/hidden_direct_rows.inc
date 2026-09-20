; State-2-only producer fast path. Caller owns a dirty, unqueued row and has
; NMI masked. Main code cannot mutate the NES shadow between the two DMAs.
; Scratch $55A0..55BF (optional paired rows: ..55DF) is separate from OAM.
; Never touches queued staging bytes. Ready states 2/3 keep the old publisher.
.macro hidden_high_groups bottom
.ifdef EXPERIMENTAL_HIDDEN_COMPACT_INDEX
    ldy $10
.endif
    .repeat 8, group
.ifndef EXPERIMENTAL_HIDDEN_COMPACT_INDEX
        ldy $10
.endif
        lda [$04],y
.if bottom
        and #$00F0
        lsr
        lsr
.else
        and #$000F
        asl
        asl
.endif
.ifdef EXPERIMENTAL_HIDDEN_COMPACT_INDEX
        ora $08             ; bit 6 selects the precomputed pattern half
.endif
        tax
        .repeat 2, pair
            lda f:$C00000+hidden_high_pairs+pair*2,x
.ifndef EXPERIMENTAL_HIDDEN_COMPACT_INDEX
            ora $08
.endif
            sta f:$7E55A0+group*4+pair*2
        .endrepeat
.ifdef EXPERIMENTAL_HIDDEN_COMPACT_INDEX
        iny
.else
        inc $10
.endif
    .endrepeat
.ifdef EXPERIMENTAL_HIDDEN_COMPACT_INDEX
    sty $10
    dey                     ; preserve the old final Y as well as $10
.endif
.endmacro
prepare_hidden_direct_row:
    .a16
    ; Capture physical low-byte source and logical destination before lookup
    ; indexing reuses X/Y. Both remain stable for an eligible mirrored row.
    tya
    clc
    adc $00
    sta $1C
    txa
    lsr
    clc
    adc #$2000
    sta $1E
.ifdef EXPERIMENTAL_HIDDEN_DIRECT_PAIR
    ; Adjacent even/odd tile rows share the complete attribute quadrant.
    ; Batch only two owned rows with equal alias eligibility. Otherwise
    ; keep the scalar path, including mixed queued/dirty alias states.
    stz $22
    lda #32
    sta $24
    lda $14
    and #1
    bne @single
    lda $1C6B
    and #$00FF
    cmp #2
    bcc @single
    lda $1C6C
    and #$00FF
    cmp #2
    bcc @single
    ldx $14
    lda $1D01,x
    and #$00FF
    cmp #1
    bne @single
    lda $1C18
    and #1
    beq @pair_vertical
    txa
    eor #$0020
    bra @pair_alias
@pair_vertical:
    txa
    eor #$0040
@pair_alias:
    tax
    lda $1D00,x
    cmp #$0101
    beq @paired
    and #$00FF
    cmp #1
    beq @single
    lda $1D01,x
    and #$00FF
    cmp #1
    beq @single
@paired:
    lda #1
    sta $22
    lda #64
    sta $24
@single:
.endif
.ifdef EXPERIMENTAL_HIDDEN_HIGH_CACHE
    ; Physical attribute group addresses are eight-byte aligned. Bit 1 keys
    ; the vertical quadrant. Pattern half and shadow cannot change within
    ; this NMI-masked producer invocation; entry invalidates the cached key.
    lda $04
    clc
    adc $10
    ora $12
    cmp $20
    bne :+
    jmp @converted
:
    sta $20
.endif
    ; Each output word is two identical tile high bytes. Prepare the pattern
    ; selector once; table entries already duplicate the two palette bytes.
    ; This removes five instructions from each of sixteen attribute pairs.
    lda $0E
.ifdef EXPERIMENTAL_HIDDEN_COMPACT_INDEX
    lsr
    lsr                     ; pattern tile bit $0100 becomes table index $40
    sta $08
.else
    xba
    and #$00FF
    sta $08
    xba
    ora $08
    sta $08
.endif
    lda $12
    bne :+
    jmp @top
:
    hidden_high_groups 1
    jmp @converted
@top:
    hidden_high_groups 0
@converted:
.ifdef EXPERIMENTAL_HIDDEN_DIRECT_PAIR
    lda $22
    beq :+
    ; Two identical high-byte rows, copied only for an eligible pair. Keep
    ; this common to both quadrant paths to fit the production code bank.
    phb
    ldx #$55A0
    ldy #$55C0
    lda #31
    mvn $7E0000,$7E0000
    plb
:
.endif
    sep #$20
    .a8
    lda #$80
    sta $2100              ; mandatory even if no consumer ran this frame
    jsr hidden_direct_dma
    ldx $14
    jsr hidden_direct_retire
.ifdef EXPERIMENTAL_HIDDEN_DIRECT_PAIR
    lda $22
    beq :+
    inx
    jsr hidden_direct_retire
:
.endif
    rep #$20
    .a16
    lda $1C18
    and #1
    beq @vertical
    lda $14
    eor #$0020
    bra @alias
@vertical:
    lda $14
    eor #$0040
@alias:
    tax
    lda $1D00,x
    and #$00FF
    cmp #1
    bne @done
    stx $1A
    txa
    .repeat 5
        asl
    .endrepeat
    clc
    adc #$2000
    sta $1E
    sep #$20
    .a8
    jsr hidden_direct_dma
    ldx $1A
    jsr hidden_direct_retire
.ifdef EXPERIMENTAL_HIDDEN_DIRECT_PAIR
    lda $22
    beq :+
    inx
    jsr hidden_direct_retire
:
.endif
@done:
    sep #$20
    .a8
.ifdef EXPERIMENTAL_HIDDEN_DIRECT_PAIR
    lda $22
    beq :+
    ; The surrounding loop accounts for the final row normally. Account
    ; for the extra consumed row here, without changing its total budget.
    inc $14
    dec $1C6B
    dec $1C6C
:
.endif
    rts
hidden_direct_retire:
    .a8
    stz $1D00,x
    lda $1E80,x
    beq :+
    dec $1E80,x
:
    rts
hidden_direct_dma:
    .a8
    stz $4300
    stz $2115              ; low port increments each word
    lda #$18
    sta $4301
    ldx $1E
    stx $2116
    ldx $1C
    stx $4302
    lda #$7F
    sta $4304
.ifdef EXPERIMENTAL_HIDDEN_DIRECT_PAIR
    ldx $24
.else
    ldx #32
.endif
    stx $4305
    lda #1
    sta $420B
    lda #$80
    sta $2115              ; high port increments each word
    lda #$19
    sta $4301
    ldx $1E
    stx $2116
    ldx #$55A0
    stx $4302
    lda #$7E
    sta $4304
.ifdef EXPERIMENTAL_HIDDEN_DIRECT_PAIR
    ldx $24
.else
    ldx #32
.endif
    stx $4305
    lda #1
    sta $420B
    rts

; Only the selected attribute nibble matters. Sixteen four-byte entries
; cover both vertical halves without two redundant 1-KiB tables.
hidden_high_pairs:
.ifdef EXPERIMENTAL_HIDDEN_COMPACT_INDEX
    .repeat 2, half
        .repeat 16, attribute
            .word (((attribute & 3) << 2) | half) * $0101
            .word ((((attribute >> 2) & 3) << 2) | half) * $0101
        .endrepeat
    .endrepeat
.else
    .repeat 16, attribute
        .word ((attribute & 3) << 2) * $0101
        .word (((attribute >> 2) & 3) << 2) * $0101
    .endrepeat
.endif
