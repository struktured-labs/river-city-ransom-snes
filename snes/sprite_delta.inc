; Exact incremental NES OAM conversion. A8, I16, DB=0, D=$1E00;
; called inside the masked producer. $08/$0A are producer scratch only.
; Temporarily uses DB=$7E for short WRAM accesses; restores DB before return.
; Snapshot and output are updated together, before the next consumer can run.
prepare_sprite_delta:
    lda $1C79
    beq @force
    lda $1C20
    and #8
    cmp $1C86
    bne @force
.ifdef EXPERIMENTAL_OAM_DIRTY_GATE
    lda $1C87
    bne :+
    rts
:
.endif
    rep #$20
    .a16
    stz $0A
    bra @begin
@force:
    rep #$20
    .a16
    lda #1
    sta $0A
@begin:
    sep #$20
    .a8
    lda $1C20
    and #8
    sta $1C86
    lsr
    lsr
    lsr
    sta $08
    phb
    lda #$7E
    pha
    plb
    rep #$20
    .a16
    ; Invalidate once on initialization or a pattern-half change. Complement
    ; each input word, so every subsequent comparison must fail, even if the
    ; old snapshot happens to equal the new input. The completed snapshot is
    ; still exact. No interrupt can observe this temporary invalidation.
    lda $0A
    beq @compare
    ldx #0
@invalidate:
    lda $1000,x
    eor #$FFFF
    sta $5600,x
    inx
    inx
    cpx #256
    bne @invalidate
@compare:
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    ; At most two changed words per sprite: 128 increments cannot wrap A8.
    ; Accumulate locally instead of repeating an absolute generation store
    ; in every unrolled branch. A pending upload must survive a no-op pass.
    phy
    ldy #0
.endif
    ; Update Y/tile and attribute/X independently. Moving only X must not
    ; redo Y conversion, and a tile animation must not redo attributes.
    ; ROM lookups use an explicit HiROM bank while DB selects WRAM.
    .repeat 64, sprite
    .scope
    lda $1000 + sprite*4
    cmp $5600 + sprite*4
    beq attribute_x
    sta $5600 + sprite*4
    and #$00FF
    tax
    sep #$20
    .a8
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    iny
.endif
    lda f:$C00000 + sprite_y_map,x
    sta $5001 + sprite*4
    lda $1001 + sprite*4
    sta $5002 + sprite*4
    rep #$20
    .a16
attribute_x:
    lda $1002 + sprite*4
    cmp $5602 + sprite*4
    beq next
    sta $5602 + sprite*4
    and #$00FF
    tax
    sep #$20
    .a8
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    iny
.endif
    lda f:$C00000 + sprite_attribute_map,x
    ora $08
    sta $5003 + sprite*4
    lda $1003 + sprite*4
    sta $5000 + sprite*4
    rep #$20
    .a16
next:
    .endscope
    .endrepeat
    ldx #256
@converted:
    sep #$20
    .a8
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    tya
    beq :+
    lda #1
    sta $1CEE
:
    ply
.endif
.ifdef EXPERIMENTAL_OAM_DIRTY_GATE
    stz $1C87
.endif
    lda $1C79
    bne @done
    ; Only the first producer generation initializes unused SNES entries.
@hidden:
    lda #240
    sta f:$7E5001,x
    inx
    inx
    inx
    inx
    cpx #512
    bne @hidden
    ldx #0
    lda #0
@high:
    sta f:$7E5200,x
    inx
    cpx #32
    bne @high
@done:
    plb
    rts
