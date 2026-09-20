; Producer: E=0, A16/X16, DB=0, D=$1E00. No hardware PPU writes.
; Called after original game interrupt work / PPUMASK writes, never by the
; bounded SNES VBlank consumer. Caller masks NMI for the native-mode bridge.
; Row flags: bit0=shadow dirty, bit1=immutable staged row ready for DMA.
; State 3 must drain the old staged row before preparing the newer shadow.
.ifdef EXPERIMENTAL_FUSED_ALIAS_ROWS
    .assert .defined(EXPERIMENTAL_ATTRIBUTE_LOOKUP), error, "Fused rows require attribute lookup"
.endif
.ifdef EXPERIMENTAL_VISIBLE_ATTRIBUTE_CACHE
    .assert .defined(EXPERIMENTAL_FUSED_ALIAS_ROWS), error, "Visible cache requires fused rows"
.endif
.macro attribute_lookup_group table, alias_delta, group_offset
.ifndef EXPERIMENTAL_VISIBLE_ATTRIBUTE_CACHE
    phy
    ldy $10
    lda [$04],y
    and #$00FF
    asl
    asl
    tay
    lda a:table,y
    ora $0E
    sta $0A
    iny
    iny
    lda a:table,y
    ora $0E
    sta $0C
    ply
.endif
    .repeat 2, pair
        .repeat 2, tile
            lda [$00],y
            and #$00FF
.ifdef EXPERIMENTAL_VISIBLE_ATTRIBUTE_CACHE
            ora a:$1B60 + group_offset/2 + pair*2
.else
            ora $0A + pair*2
.endif
.ifdef EXPERIMENTAL_FUSED_ALIAS_ROWS
            sta f:$7E3000 + group_offset + pair*4 + tile*2,x
.if alias_delta <> 0
            sta f:$7E3000 + alias_delta + group_offset + pair*4 + tile*2,x
.endif
.else
.ifdef EXPERIMENTAL_ROW_STORES
            sta f:$7E3000 + pair*4 + tile*2,x
.if alias_delta <> 0
            sta f:$7E3000 + alias_delta + pair*4 + tile*2,x
.endif
.else
            sta f:$7E3000,x
.if alias_delta <> 0
            sta f:$7E3000 + alias_delta,x
.endif
            inx
            inx
.endif
.endif
            iny
        .endrepeat
    .endrepeat
.if .defined(EXPERIMENTAL_ROW_STORES) .and .not .defined(EXPERIMENTAL_FUSED_ALIAS_ROWS)
    txa
    clc
    adc #8
    tax
.endif
.ifndef EXPERIMENTAL_VISIBLE_ATTRIBUTE_CACHE
    inc $10
.endif
.endmacro
.macro attribute_lookup_groups table, alias_delta
.ifdef EXPERIMENTAL_FUSED_ALIAS_ROWS
    ; All eight groups have fixed destination offsets. Keep X at the row
    ; base throughout and advance once, removing per-tile/index bookkeeping.
    .repeat 8, group
        attribute_lookup_group table, alias_delta, group*8
    .endrepeat
    txa
    clc
    adc #64
    tax
.else
    lda #8
    sta $18
:
    attribute_lookup_group table, alias_delta, 0
    dec $18
    bne :-
.endif
.endmacro

.ifdef EXPERIMENTAL_CONTROL_PRESETS
; Optional two-line SNES-only control row in the otherwise unchanged original
; message-speed/skill settings screen. Reuse original uppercase font tiles.
; Never write to original game RAM; dirty the same NES-shadow rows as $2007.
prepare_control_menu:
    php
    phx
    phy
    lda $0006
    and #$00FF
    cmp #5
    beq :+
    jmp @end
:
    lda $010B
    and #$00FF
    cmp #1
    beq :+
    jmp @end
:
    lda $0519
    and #$00FF
    beq :+
    jmp @end
:
    lda $1CF8
    and #$00FF
    asl
    asl
    asl
    asl
    asl
    asl                     ; mode * 64 bytes: two 32-tile lines
    tax
    sep #$20
    .a8
    lda #$E0
    sta $10                 ; physical original CIRAM row 23, column 0
    lda #$22
    sta $11
    lda #$7F
    sta $12
    ldy #0
@first:
    lda f:control_menu_text,x
    jsr @tile
    cmp [$10],y
    beq :+
    sta [$10],y
    lda $1D17
    ora #1
    sta $1D17
    lda $1D57
    ora #1
    sta $1D57
    lda #1
    sta $1C85
:
    inx
    iny
    cpy #32
    bne @first
    stz $10
    lda #$23
    sta $11                 ; original CIRAM row 24, column 0
    ldy #0
@second:
    lda f:control_menu_text,x
    jsr @tile
    cmp [$10],y
    beq :+
    sta [$10],y
    lda $1D18
    ora #1
    sta $1D18
    lda $1D58
    ora #1
    sta $1D58
    lda #1
    sta $1C85
:
    inx
    iny
    cpy #32
    bne @second
@end:
    ply
    plx
    plp
    rts
@tile:
    cmp #$20
    bne :+
    lda #0
    rts
:
    clc
    adc #$7F                ; ASCII A..Z -> original font tiles C0..D9
    rts
control_menu_text:
    .byte " CLASSIC B PUNCH Y KICK A JUMP  "
    .byte "    L R CHANGE CONTROL MODE     "
    .byte " NINTENDO A PUNCH B KICK X JUMP "
    .byte "    L R CHANGE CONTROL MODE     "
    .byte "  ARCADE Y PUNCH X KICK B JUMP  "
    .byte "    L R CHANGE CONTROL MODE     "
    .byte " REVERSE Y PUNCH B KICK A JUMP  "
    .byte "    L R CHANGE CONTROL MODE     "
.assert * - control_menu_text = 256, error, "Control menu text must be four pairs of 32 tiles"
.endif

native_prepare:
.ifdef EXPERIMENTAL_VISIBLE_ATTRIBUTE_CACHE
    .a16
    ; Invocation-local: the masked bridge prevents NES attribute/pattern
    ; writes during this call. Separate from hidden DMA's key/scratch.
    lda #$FFFF
    sta $26
.endif
.ifdef EXPERIMENTAL_HIDDEN_HIGH_CACHE
    .a16
    ; Invocation-local only: main code may change attributes/patterns between
    ; calls. D=$1E00; $20..21 are private scratch, never original game RAM.
    lda #$FFFF
    sta $20
.endif
.ifdef EXPERIMENTAL_CONTROL_PRESETS
    jsr prepare_control_menu
.endif
    ; A background pattern-table change invalidates each staged tile's bit 8.
    sep #$20
    .a8
    lda $1C20
    and #$10
    cmp $1C78
    beq @rows_start
    sta $1C78
    lda #1
    sta $1C85
    ; Seed and forward-copy the same dirty byte across all 128 flags.
    ; MVN changes DB; restore it before returning to the producer.
    sta $1D00
    rep #$20
    .a16
    phb
    ldx #$1D00
    ldy #$1D01
    lda #126
    mvn $7E0000,$7E0000
    plb
    sep #$20
    .a8
@rows_start:
    lda $1C79
    beq @scan_rows
    lda $1C85
    bne @scan_rows
    jmp prepare_palette
@scan_rows:
.ifdef EXPERIMENTAL_VISIBLE_ROW_PHASE
    ; Decide before consuming the dirty-work latch. A deferred pass leaves
    ; cursor, ownership, staged bytes and pending-work indication untouched.
    jsr visible_row_phase_budget
    bne :+
    jmp prepare_palette
:
    sta $1C6B
.endif
    stz $1C85
    rep #$20
    .a16
    lda $1C76
    and #$007F
    tax
    sep #$20
    .a8
    ; Menu/load work may opt into one additional row; gameplay retains its
    ; two-row budget and therefore its established camera/encounter timing.
    lda $0100
    and #$C0
    cmp #$C0
    beq @game_budget
.ifdef LOAD_ROW_BUDGET
    lda #LOAD_ROW_BUDGET
.else
    lda #4
.endif
    bra @set_budget
@game_budget:
.ifdef HIDDEN_ROW_BUDGET
    ; Initial state-2 publication is hidden, even when original task=C0.
    ; Leave ordinary gameplay and rendering-off state 1 budgets unchanged.
    lda $1CA0
    cmp #2
    bne :+
    lda #HIDDEN_ROW_BUDGET
    bra @set_budget
:
.endif
.ifdef EXPERIMENTAL_TRANSITION_WAIT_PREPARE
    lda $1CF7
    bne @transition_one_row
    lda $1CA0
    cmp #2
    bne @transition_normal_budget
    lda $1CF0
    bne @transition_fallback
    lda #1
    sta $1CF0
    inc $1CF1
    bne @transition_one_row
    inc $1CF2
@transition_one_row:
    lda #1
    bra @set_budget
@transition_fallback:
    inc $1CF5
    bne @transition_normal_budget
    inc $1CF6
@transition_normal_budget:
.endif
.ifdef EXPERIMENTAL_VISIBLE_ROW_PHASE
    lda $1C6B
.else
.ifdef EXPERIMENTAL_GAMEPLAY_PREPARE_DEFER
    lda #4
.elseif .defined(GAMEPLAY_ROW_BUDGET)
    lda #GAMEPLAY_ROW_BUDGET
.else
    lda #2
.endif
.endif
@set_budget:
    sta $1C6B
    lda #128
    sta $1C6C
@rows:
    sep #$20
    .a8
.ifdef EXPERIMENTAL_ROW_SCAN
    ; Skip eight rows only when none has a dirty-shadow bit. State 3 must
    ; still use the scalar path; never cross the flags array or scan budget.
    cpx #121
    bcs @scalar_scan
    lda $1C6C
    cmp #8
    bcc @scalar_scan
    rep #$20
    .a16
    lda $1D00,x
    ora $1D02,x
    ora $1D04,x
    ora $1D06,x
    and #$0101
    bne @scalar_width
    txa
    clc
    adc #8
    tax
    cpx #128
    bcc :+
    ldx #0
:
    sep #$20
    .a8
    lda $1C6C
    sec
    sbc #8
    sta $1C6C
    beq @prepared
    bra @rows
@scalar_width:
    sep #$20
    .a8
@scalar_scan:
.endif
    lda $1D00,x
    cmp #1
    beq @convert
@next:
    inx
    cpx #128
    bcc :+
    ldx #0
:
    dec $1C6C
    beq @prepared
    lda $1C6B
    bne @rows
@prepared:
    txa
    sta $1C76
    jmp prepare_palette
@convert:
    rep #$20
    .a16
    stx $14
    txa
    and #$0060
    sta $00
    lda $1C18
    and #1
    beq :+
    lsr $00                ; horizontal: tables 0/1 share A, 2/3 share B
:
    lda $00
    and #$0020             ; vertical: tables 0/2 share A, 1/3 share B
    xba
    lsr
    lsr
    lsr
    ora #$2000
    sta $00
    clc
    adc #$03C0
    sta $04
    txa
    and #$0060
    xba
    lsr
    lsr
    sta $16
    sep #$20
    .a8
    lda #$7F
    sta $02
    sta $06
    rep #$20
    .a16
    txa
    and #$001F
    cmp #30
    bcc :+
    sep #$20
    .a8
    stz $1D00,x
    jmp @next
:
    .a16
    asl
    asl
    asl
    asl
    asl
    tay
    asl
    clc
    adc $16
    tax
    lda $1C20
    and #$0010
    asl
    asl
    asl
    asl
    sta $0E                 ; pattern-half tile bit, constant across the row
    lda $14
    and #$001C
    asl
    sta $10                 ; first attribute byte for this tile row
    lda $14
    and #2
    sta $12                 ; bottom half of the attribute quadrant
.ifdef EXPERIMENTAL_HIDDEN_DIRECT_ROWS
    lda $1CA0
    and #$00FF
    cmp #2
    bne :+
    jsr prepare_hidden_direct_row
    jmp @row_budget_done
:
.endif
.ifdef EXPERIMENTAL_PLANAR_ROWS
    jsr prepare_planar_row
.else
.ifdef EXPERIMENTAL_ATTRIBUTE_LOOKUP
.ifdef EXPERIMENTAL_FUSED_ALIAS_ROWS
    jsr prepare_fused_attribute_row
.else
    lda $12
    bne :+
    jmp @attribute_top
:
    attribute_lookup_groups attribute_palette_bottom, 0
    jmp @attribute_done
@attribute_top:
    attribute_lookup_groups attribute_palette_top, 0
@attribute_done:
.endif
.else
    lda #8
    sta $18                 ; eight groups of four tiles
@group:
    phy
    ldy $10
    lda [$04],y
    and #$00FF
    sta $0C
    lda $12
    beq :+
    lda $0C
    lsr
    lsr
    lsr
    lsr
    sta $0C
:
    ply
    .repeat 2, pair
        lda $0C
        .if pair
            lsr
            lsr
        .endif
        and #3
        xba
        asl
        asl
        ora $0E
        sta $0A
        .repeat 2, tile
            lda [$00],y
            and #$00FF
            ora $0A
.ifdef EXPERIMENTAL_ROW_STORES
            sta f:$7E3000 + pair*4 + tile*2,x
.else
            sta f:$7E3000,x
            inx
            inx
.endif
            iny
        .endrepeat
    .endrepeat
.ifdef EXPERIMENTAL_ROW_STORES
    txa
    clc
    adc #8
    tax
.endif
    inc $10
    dec $18
    bne @group
.endif
.endif
    ldx $14
    sep #$20
    .a8
    lda #2
    sta $1D00,x
.if .not .defined(EXPERIMENTAL_FUSED_ALIAS_ROWS) .and .not .defined(EXPERIMENTAL_PLANAR_ROWS)
    jsr prepare_row_alias
.endif
.ifdef EXPERIMENTAL_HIDDEN_DIRECT_ROWS
@row_budget_done:
    ldx $14
    sep #$20
    .a8
.endif
    dec $1C6B
    bne :+
    lda #1
    sta $1C85              ; work beyond this call's row budget may remain
:
    jmp @next
.ifdef EXPERIMENTAL_FUSED_ALIAS_ROWS
; Conversion already has the tile word in A. A second store is cheaper than
; rereading the completed row through MVN/native copying. Only dirty state 1
; may be fused; ready states 2/3 must preserve their immutable old snapshot.
; The native bridge masks NMI across this producer; publish alias-ready only
; after all 32 words have been written. $1A is private producer scratch.
.macro fused_attribute_kernel delta
.ifdef EXPERIMENTAL_VISIBLE_ATTRIBUTE_CACHE
    ; Cache contents already select the proper vertical quadrant.
    attribute_lookup_groups attribute_palette_top, delta
.else
    .local top, done
    lda $12
    bne :+
    jmp top
:
    attribute_lookup_groups attribute_palette_bottom, delta
    jmp done
top:
    attribute_lookup_groups attribute_palette_top, delta
done:
.endif
.endmacro
.ifdef EXPERIMENTAL_VISIBLE_ATTRIBUTE_CACHE
.macro visible_attribute_words table
    .repeat 8, group
        ldy $10
        lda [$04],y
        and #$00FF
        asl
        asl
        tay
        lda a:table,y
        ora $0E
        sta a:$1B60+group*4
        iny
        iny
        lda a:table,y
        ora $0E
        sta a:$1B62+group*4
        inc $10
    .endrepeat
.endmacro
prepare_visible_attribute_cache:
    .a16
    ; Private low-WRAM $1B60..1B7F: sixteen palette/pattern words for this
    ; physical attribute row/quadrant, directly addressed with DB=0. X untouched,
    ; tile-source Y preserved. $10 may advance; each row's setup rebuilds it.
    phy
    lda $04
    clc
    adc $10
    ora $12
    cmp $26
    bne @miss
    ply
    rts
@miss:
    sta $26
    lda $12
    bne :+
    jmp @top
:
    visible_attribute_words attribute_palette_bottom
    ply
    rts
@top:
    visible_attribute_words attribute_palette_top
    ply
    rts
.endif
.ifdef EXPERIMENTAL_VISIBLE_ROW_PHASE
    .include "visible_row_phase.inc"
.endif
prepare_fused_attribute_row:
    .a16
.ifdef EXPERIMENTAL_VISIBLE_ATTRIBUTE_CACHE
    jsr prepare_visible_attribute_cache
.endif
    phx
    lda $1C18
    and #1
    beq fused_vertical_alias
    lda $14
    eor #$0020
    bra fused_alias_index
fused_vertical_alias:
    lda $14
    eor #$0040
fused_alias_index:
    tax
    lda $1D00,x
    and #$00FF
    cmp #1
    bne :+
    jmp fused_dirty_alias
:
    plx
    fused_attribute_kernel 0
    rts
fused_dirty_alias:
    stx $1A
    plx
    lda $1C18
    and #1
    bne :+
    jmp fused_vertical_direction
:
    lda $14
    and #$0020
    beq :+
    jmp fused_horizontal_negative
:
    fused_attribute_kernel $0800
    jmp fused_publish_alias
fused_horizontal_negative:
    fused_attribute_kernel -$0800
    jmp fused_publish_alias
fused_vertical_direction:
    lda $14
    and #$0040
    beq :+
    jmp fused_vertical_negative
:
    fused_attribute_kernel $1000
    jmp fused_publish_alias
fused_vertical_negative:
    fused_attribute_kernel -$1000
fused_publish_alias:
    ldx $1A
    sep #$20
    .a8
    lda #2
    sta $1D00,x
    rep #$20
    .a16
    rts
.endif
.ifdef EXPERIMENTAL_ALIAS_WORD_COPY
.macro alias_words
    .repeat 32, word
        lda a:word*2,x
        sta a:word*2,y
    .endrepeat
.endmacro
.endif
prepare_row_alias:
    ; Both logical rows display the same physical row. Only a dirty, unqueued
    ; alias may receive this snapshot; states 2/3 remain immutable for DMA.
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
    stx $18
    sep #$20
    .a8
    lda $1D00,x
    cmp #1
.ifdef EXPERIMENTAL_ALIAS_WORD_COPY
    beq :+
    jmp @done
:
.else
    bne @done
.endif
    rep #$20
    .a16
    lda $14
    .repeat 6
        asl
    .endrepeat
    clc
    adc #$3000
    tax
    lda $18
    .repeat 6
        asl
    .endrepeat
    clc
    adc #$3000
    tay
    phb
.ifdef EXPERIMENTAL_ALIAS_WORD_COPY
    ; Staging is outside bank-zero's low WRAM mirror. Select DB=7E and
    ; copy 32 words using the existing MVN source X / destination Y bases.
    ; Both bases are inside $3000..$4FC0, so offsets 0..62 cannot wrap.
    ; Queued aliases were rejected above, before touching their bytes.
    sep #$20
    .a8
    lda #$7E
    pha
    plb
    rep #$20
    .a16
    alias_words
    ; Preserve MVN's caller-visible destination-end Y, as well as DB below.
    tya
    clc
    adc #64
    tay
.else
    lda #63
    mvn $7E0000,$7E0000
.endif
    plb
    ldx $18
    sep #$20
    .a8
    lda #2
    sta $1D00,x
@done:
    ldx $14
    rts

.ifdef EXPERIMENTAL_PLANAR_ROWS
    .include "planar_rows.inc"
.endif
.ifdef EXPERIMENTAL_HIDDEN_DIRECT_ROWS
    .include "hidden_direct_rows.inc"
.endif
prepare_palette:
    ; Compare the actual shadow, not write flags: original code may rewrite
    ; identical palettes every frame. The first publication always converts.
    lda $1C79
    beq @changed
    rep #$20
    .a16
    ldx #0
@compare:
    lda f:$7F3F00,x
    cmp f:$7E5580,x
    bne @palette_changed16
    inx
    inx
    cpx #32
    bne @compare
    sep #$20
    .a8
    jmp prepare_sprites
@changed:
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    lda #1
    sta $1CED
.endif
    rep #$20
    .a16
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    bra @snapshot
.endif
@palette_changed16:
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    sep #$20
    .a8
    lda #1
    sta $1CED
    rep #$20
    .a16
.endif
@snapshot:
    ldx #0
@copy:
    lda f:$7F3F00,x
    sta f:$7E5580,x
    inx
    inx
    cpx #32
    bne @copy
    sep #$20
    .a8
    ldy #0
@bg:
    tya
    and #3
    bne :+
    lda f:$7F3F00
    bra @color
:
    tyx
    lda f:$7F3F00,x
@color:
    jsr native_color
    .a16
    sta $08
    tya
    asl
    tax
    lda $08
    sta f:$7E5400,x
    sep #$20
    .a8
    iny
    cpy #16
    bne @bg
    ldy #0
@obj:
    tyx
    lda f:$7F3F10,x
    jsr native_color
    .a16
    sta $08
    tya
    and #12
    asl
    asl
    asl
    sta $0A
    tya
    and #3
    asl
    ora $0A
    tax
    lda $08
    sta f:$7E5500,x
    sep #$20
    .a8
    iny
    cpy #16
    bne @obj
prepare_sprites:
.ifdef EXPERIMENTAL_HIDDEN_SPRITE_DEFER
    ; Only skip while an actual required, unqueued row prevents exposure.
    ; Checking the next producer cursor avoids scanning a whole row ring.
    ; Do not clear sprite dirtiness/cache: the first nonblocked producer
    ; must prepare current OAM before the consumer can reveal the screen.
    lda $1C79
    beq @sprite_work
    lda $1CA0
    cmp #2
    bne @sprite_work
    rep #$20
    .a16
    lda $1C76
    and #$007F
    tax
    sep #$20
    .a8
    lda $1D00,x
    cmp #1
    bne @sprite_work
    lda $1E80,x
    beq @sprite_work
    jmp prepare_tail
@sprite_work:
.endif
.ifdef EXPERIMENTAL_SPRITE_DELTA
    jsr prepare_sprite_delta
    jmp prepare_tail
.endif
; The delta producer above unconditionally bypasses this scalar implementation.
; Omit its unreachable bytes in the generation-gated combination, leaving the
; disabled comparison cartridge byte-identical and keeping shared LUTs below.
.if (.defined(EXPERIMENTAL_SPRITE_DELTA) = 0) .or (.defined(EXPERIMENTAL_DIRTY_FINAL_DMA) = 0)
    lda $1C79
    beq @changed
    lda $1C20
    and #8
    cmp $1C86
    bne @changed
.ifdef EXPERIMENTAL_OAM_DIRTY_GATE
    ; $1000 OAM shadow changes only through the translated $2004/$4014
    ; paths.  Avoid a full 256-byte equality scan until either path runs.
    lda $1C87
    bne :+
    jmp prepare_tail
:
.endif
    rep #$20
    .a16
    ldx #0
@compare:
.ifdef EXPERIMENTAL_OAM_COMPARE_UNROLL
    ; Eight unchanged words share one index update.  CMP equality leaves
    ; carry set, so ADC #15 advances exactly 16 bytes without a CLC.
    .repeat 8, word
        lda $1000 + word*2,x
        cmp f:$7E5600 + word*2,x
        bne @sprite_changed16
    .endrepeat
    txa
    adc #15
    tax
    cpx #256
    bne @compare
.else
    lda $1000,x
    cmp f:$7E5600,x
    bne @sprite_changed16
    inx
    inx
    cpx #256
    bne @compare
.endif
    sep #$20
    .a8
.ifdef EXPERIMENTAL_OAM_DIRTY_GATE
    stz $1C87
.endif
    jmp prepare_tail
@changed:
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    lda #1
    sta $1CEE
.endif
    rep #$20
    .a16
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    bra @snapshot
.endif
@sprite_changed16:
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    sep #$20
    .a8
    lda #1
    sta $1CEE
    rep #$20
    .a16
.endif
@snapshot:
    ; Native block copy is safe inside the already-masked producer bridge.
    phb
    ldx #$1000
    ldy #$5600
    lda #255
    mvn $7E0000,$7E0000
    plb
    sep #$20
    .a8
    lda $1C20
    and #8
    sta $1C86
    lsr
    lsr
    lsr
    sta $08                ; shared OBJ pattern-half bit for this snapshot
.ifdef EXPERIMENTAL_SPRITE_UNROLL
    ; Keep accumulator B zero so A8 -> I16 TAY produces a 0..255 table index.
    ; Fully unrolling removes the four INX operations and loop branch from all
    ; 64 sprites while retaining the exact NES-to-SNES byte permutation.
    rep #$20
    .a16
    lda #0
    sep #$20
    .a8
    .repeat 64, sprite
        lda $1003 + sprite*4
        sta f:$7E5000 + sprite*4
        lda $1000 + sprite*4
        tay
        lda sprite_y_map,y
        sta f:$7E5001 + sprite*4
        lda $1001 + sprite*4
        sta f:$7E5002 + sprite*4
        lda $1002 + sprite*4
        tay
        lda sprite_attribute_map,y
        ora $08
        sta f:$7E5003 + sprite*4
    .endrepeat
    ldx #256
    bra @sprites_done
.endif
    ; 8x8 NES sprites, preserved ordering, flips and palette indices.
    ldx #0
@sprites:
    lda $1003,x
    sta f:$7E5000,x
    lda $1000,x
    cmp #239
    bcc @visible_sprite
    lda #240
    bra @sprite_y
@visible_sprite:
    clc
    adc #2
@sprite_y:
    sta f:$7E5001,x
    lda $1001,x
    sta f:$7E5002,x
    rep #$20
    .a16
    lda $1002,x
    and #$00FF
    tay
    sep #$20
    .a8
    lda sprite_attribute_map,y
    ora $08
    sta f:$7E5003,x
    inx
    inx
    inx
    inx
    cpx #256
    bne @sprites
@sprites_done:
.ifdef EXPERIMENTAL_OAM_DIRTY_GATE
    stz $1C87
.endif
    lda $1C79
    bne prepare_tail
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
@high_oam:
    lda #0
    sta f:$7E5200,x
    inx
    cpx #32
    bne @high_oam
.endif

prepare_tail:
    jsr prepare_chr
    lda #1
    sta $1C79
    rep #$20
    .a16
    rts

native_color:
    ; A8 palette index -> A16 RGB555; X clobbered, Y retained.
    .a8
    and #$3F
    rep #$20
    .a16
    and #$00FF
    asl
    tax
    lda native_palette,x
    rts

prepare_chr:
    .a8
.ifdef EXPERIMENTAL_CHR_DIRTY_GATE
    ; CHR jobs depend only on R0..R5, MMC3 inversion, and PPUCTRL pattern
    ; selection. Their translated write paths set this latch. The first
    ; producer still scans unconditionally before $1C79 becomes initialized.
    lda $1C79
    beq @chr_dirty
    lda $1CBB
    bne @chr_dirty
    rts
@chr_dirty:
    stz $1CBB
.endif
    ldy #0
@slot:
    sty $18
    rep #$20
    .a16
    tya
    ; MMC3 CHR inversion changes which registers feed a physical PPU slot,
    ; not the destination slot. The CPU-side CHR reader already honors it.
    pha
    lda $1C19
    and #$0080
    beq :+
    pla
    eor #4
    bra @mapped_slot
:
    pla
@mapped_slot:
    sta $10
    cmp #4
    bcs @single
    lsr
    tax
    lda $1C10,x
    and #$00FE
    sta $12
    lda $10
    and #1
    ora $12
    bra @bank
@single:
    sec
    sbc #2
    tax
    lda $1C10,x
    and #$007F
@bank:
    and #$007F
    sta $12
    ; BG job = slot. Only queue the selected background pattern half.
    tya
    tax
    sep #$20
    .a8
    tya
    and #4
    asl
    asl
    eor $1C20
    and #$10
    bne @no_bg
    lda $12
    cmp $1DA0,x
    beq @obj
    sta $1DA0,x
    lda #1
    sta $1D80,x
    rep #$20
    .a16
    txa
    asl
    asl
    asl
    tax
    lda $12
    xba
    asl
    asl
    sta $1500,x
    lda $12
    lsr
    lsr
    lsr
    lsr
    lsr
    lsr
    clc
    adc #$00C9
    sta $1502,x
    tya
    xba
    asl
    sta $1504,x
    lda #1024
    sta $1506,x
    sep #$20
    .a8
    bra @obj
@no_bg:
    lda #$FF
    sta $1DA0,x
    stz $1D80,x
@obj:
    rep #$20
    .a16
    tya
    asl
    clc
    adc #8
    tax
    sep #$20
    .a8
    tya
    and #4
    asl
    eor $1C20
    and #8
    bne @no_obj
    lda $12
    cmp $1DA0,x
    beq @next
    sta $1DA0,x
    sta $1DA1,x
    lda #1
    sta $1D80,x
    stz $1D81,x
    rep #$20
    .a16
    txa
    asl
    asl
    asl
    tax
    lda $12
    xba
    asl
    asl
    asl
    sta $1500,x
    clc
    adc #1024
    sta $1508,x
    lda $12
    lsr
    lsr
    lsr
    lsr
    lsr
    clc
    adc #$00CB
    sta $1502,x
    sta $150A,x
    tya
    xba
    asl
    asl
    clc
    adc #$4000
    sta $1504,x
    clc
    adc #512
    sta $150C,x
    lda #2048
    sta $1506,x
    sep #$20
    .a8
    bra @next
@no_obj:
    lda #$FF
    sta $1DA0,x
    sta $1DA1,x
    stz $1D80,x
    stz $1D81,x
@next:
    ldy $18
    iny
    cpy #8
    beq :+
    jmp @slot
:
    rts
.ifdef EXPERIMENTAL_SPRITE_DELTA
    .include "sprite_delta.inc"
.endif
sprite_attribute_map:
    .repeat 256, attribute
        .if attribute & $20
            .byte (attribute & $C0) | ((attribute & 3) << 1)
        .else
            .byte (attribute & $C0) | ((attribute & 3) << 1) | $30
        .endif
    .endrepeat
.if .defined(EXPERIMENTAL_SPRITE_UNROLL) .or .defined(EXPERIMENTAL_SPRITE_DELTA)
sprite_y_map:
    .repeat 256, coordinate
        .if coordinate < 239
            .byte coordinate + 2
        .else
            .byte 240
        .endif
    .endrepeat
.endif
.ifdef EXPERIMENTAL_ATTRIBUTE_LOOKUP
attribute_palette_top:
    .repeat 256, attribute
        .word ((attribute & 3) << 10), (((attribute >> 2) & 3) << 10)
    .endrepeat
attribute_palette_bottom:
    .repeat 256, attribute
        .word (((attribute >> 4) & 3) << 10), (((attribute >> 6) & 3) << 10)
    .endrepeat
.endif
native_palette:
    .include "native_palette.inc"
