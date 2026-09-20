; Bounded NMI consumer. A8/X16, DB=0, D=$1E00.
; No conversion or wait loops. Transitions force blank before queue writes.
; Maximum 2048 VRAM bytes (experimental state-2 forced blank: 4096),
; 544 OAM bytes and 64 CGRAM bytes per invocation. Audio runs AFTER this.
.ifdef EXPERIMENTAL_OAM_LIVE_HALF
.include "oam_live_half.inc"
.endif
native_video:
    .a8
    lda $1C79
    bne :+
    rts
:
    inc $1C7A
    lda $2137
    lda $213D
    sta $1C7C
    lda $213D
    and #1
    sta $1C7D
    ; Transition layers are already hidden. Force blank before any queue
    ; writes, allowing the same bounded batch outside the VBlank aperture.
    lda $1CA0
    beq :+
    lda #$80
    sta $2100
    jmp @on_time
:
    lda $1C7D
    ; Deferred bank-switch NMIs may arrive too late for the final OAM/CGRAM
    ; batch. Keep all queued data intact unless the full publisher fits.
    bne @late
    lda $1C7C
    cmp #243
    bcs @late
    lda $4212
    bmi @on_time
@late:
.ifdef EXPERIMENTAL_RETAINED_RETURN_EDGE
    ; A recovered fresh NMI can arrive too late for DMA, but the completed
    ; camera must still reach the next frame. These four WRAM stores touch
    ; neither queue ownership nor VRAM/OAM/CGRAM. Even a line-261 wrap leaves
    ; ample time before the first street HDMA entry at line 32.
    lda $1CA0
    bne @late_camera_done
    lda $0100
    and #$C0
    cmp #$C0
    bne @late_camera_done
    ; Use the just-latched beam, so a 261 -> 0 wrap cannot discard this
    ; camera. Before line 29 also leaves >2 lines before street HDMA starts.
    lda $1C7D
    bne @late_camera_copy
    lda $1C7C
    cmp #29
    bcc @late_camera_copy
    cmp #243
    bcc @late_camera_done
@late_camera_copy:
    lda a:$00F6
    sta $1C94
    sta $1C97
    lda a:$003D
    and #1
    sta $1C95
    sta $1C98
@late_camera_done:
.endif
    rts
@on_time:
.ifdef EXPERIMENTAL_CAMERA_VBLANK_COMMIT
    ; Only accepted visible-game VBlank entries get this small independent
    ; commit. A later final_room rejection must not retain yesterday's camera.
    ; Transition publication and all descriptor/MMIO writes keep their gates.
    lda $1CA0
    bne @camera_committed
    lda $0100
    and #$C0
    cmp #$C0
    bne @camera_committed
    lda a:$00F6
    sta $1C94
    sta $1C97
    lda a:$003D
    and #1
    sta $1C95
    sta $1C98
@camera_committed:
.endif
    lda #$80
    sta $2115
    lda #1
    sta $4300
    lda #$18
    sta $4301
    rep #$20
    .a16
.ifdef EXPERIMENTAL_HIDDEN_DMA
    ; Only the state-2 forced-blank publisher gets the larger allowance.
    ; The entry above has already asserted INIDISP forced blank. Normal
    ; gameplay, rendering-off state 1, and final VBlank guards are unchanged.
    lda $1CA0
    and #$00FF
    cmp #2
    bne @normal_dma_budget
    lda #4096
    bra @dma_budget_ready
@normal_dma_budget:
    lda #2048
@dma_budget_ready:
.else
    lda #2048
.endif
    sta $1A
    lda $1C75
    and #$00FF
    tax
    ; Most NMIs have no changed CHR banks. Test the actual 24-byte job bitmap
    ; in 16-bit words instead of spending VBlank on a 24-iteration search.
    ; Keep X at the saved cursor for @rows_start; no summary flag can go stale.
    lda $1D80
    .repeat 11, pair
        ora $1D82+pair*2
    .endrepeat
    bne @chr_pending
    jmp @rows_start
@chr_pending:
    ldy #24
@chr:
    sep #$20
    .a8
    lda $1D80,x
    beq @next_chr
    rep #$20
    .a16
    lda $1A
    cmp #1024
    bcc @rows_start
    ; Preflight reserves room for up to 2 KiB plus the final palette/OAM batch.
    sep #$20
    .a8
    jsr dma_room
    bcc @rows_start
    stz $1D80,x
    rep #$20
    .a16
    phx
    txa
    asl
    asl
    asl
    tax
    lda $1500,x
    sta $4302
    lda $1504,x
    sta $2116
    sep #$20
    .a8
    lda $1502,x
    sta $4304
    rep #$20
    .a16
    lda $1506,x
    sta $4305
    sta $1E
    sep #$20
    .a8
    lda #1
    sta $420B
    rep #$20
    .a16
    lda $1A
    sec
    sbc $1E
    sta $1A
    plx
    inx
    cpx #24
    bcc :+
    ldx #0
:
    bra @rows_start
@next_chr:
    inx
    cpx #24
    bcc :+
    ldx #0
:
    dey
    bne @chr
@rows_start:
    sep #$20
    .a8
    txa
    sta $1C75
    rep #$20
    .a16
    lda $1C74
    and #$007F
    tax
    lda $1A
    bne :+
    jmp @finish
:
    ldy #32
.ifdef EXPERIMENTAL_TRANSITION_SCAN
    ; A forced-blank transition is not constrained to VBlank.  Let the
    ; consumer examine the complete 128-entry row ring so that a small final
    ; batch cannot sit behind the ordinary 32-entry scan cursor for another
    ; display frame.  The existing 2048-byte publication budget is unchanged.
    lda $1CA0
    and #$00FF
    cmp #2
    bne :+
    ldy #128
:
.endif
@row:
    sep #$20
    .a8
    ; Eight entries with no staged-ready bit are equivalent to eight scalar
    ; misses. Keep the same queue-visit budget and never read past entry 127.
    cpx #121
    bcs @scalar_row
    cpy #8
    bcc @scalar_row
    rep #$20
    .a16
    lda $1D00,x
    ora $1D02,x
    ora $1D04,x
    ora $1D06,x
    and #$0202
    bne @scalar_row_width
    txa
    clc
    adc #8
    tax
    cpx #128
    bcc :+
    ldx #0
:
    tya
    sec
    sbc #8
    tay
    beq @finish
    bra @row
@scalar_row_width:
    sep #$20
    .a8
@scalar_row:
    lda $1D00,x
    and #2
    beq @next_row
    rep #$20
    .a16
    lda $1A
    cmp #64
    bcc @finish
    sep #$20
    .a8
    ; Reserve enough time for the final palette/OAM batch after this small row.
    jsr row_room
    bcc @finish
.ifdef EXPERIMENTAL_HIDDEN_ROW_RUN
    jsr prepare_row_dma_run
.else
    jsr pair_ready_row
.endif
    ; Consume the immutable staged row, retaining a newer shadow write.
    lda $1D00,x
    and #1
    sta $1D00,x
    pha
    lda $1E80,x
    beq :+
    dec $1E80,x
:
    pla
    beq :+
    sta $1C85              ; a queued newer shadow write can now be prepared
:
    rep #$20
    .a16
.ifdef EXPERIMENTAL_PLANAR_ROWS
    jsr publish_planar_row
.else
    txa
    asl
    asl
    asl
    asl
    asl
    pha
    clc
    adc #$2000
    sta $2116
    pla
    asl
    clc
    adc #$3000
    sta $4302
    lda $1E
    sta $4305
    sep #$20
    .a8
    lda #$7E
    sta $4304
    lda #1
    sta $420B
    rep #$20
    .a16
.endif
    lda $1A
    sec
    sbc $1E
    sta $1A
.ifdef EXPERIMENTAL_HIDDEN_ROW_RUN
    jsr advance_ready_rows
    bra @next_row
.else
    lda $1E
    cmp #128
    bne @next_row
    inx
.endif
@next_row:
    inx
    cpx #128
    bcc :+
    ldx #0
:
    dey
    beq @finish
    jmp @row
@finish:
    sep #$20
    .a8
    txa
    and #$7F
    sta $1C74
    jsr transition_ready
    ; Recheck after scanning/draining queues: late entry and variable scan
    ; work must not push the unconditional final batch into active video.
    jsr final_room
    bcs :+
    rts
:
.ifdef EXPERIMENTAL_PENDING_PALETTE
    ; Stay inside the existing checked final batch. This prepares only the
    ; palette generation that the non-retained original NMI is about to copy.
    jsl $C07000
.endif
    ; Publish prepared OAM.  The producer owns the generation latch while NMI
    ; is masked; clear it only after the corresponding DMA has completed.
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    lda $1CEE
    beq @palette_batch
.endif
    stz $2102
    stz $2103
    stz $4300
    lda #4
    sta $4301
    ldx #$5000
    stx $4302
    lda #$7E
    sta $4304
.ifdef EXPERIMENTAL_OAM_LIVE_HALF
    select_oam_transfer_size
.else
    ldx #544
.endif
    stx $4305
    lda #1
    sta $420B
.ifdef EXPERIMENTAL_OAM_LIVE_HALF
    complete_oam_transfer
.endif
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    stz $1CEE
@palette_batch:
    lda $1CED
    beq @final_registers
    ; Palette-only generations may legitimately follow a frame with unchanged
    ; OAM.  Do not inherit DMA mode/source-bank initialization from the OAM
    ; branch that was just skipped.
    stz $4300
    lda #$7E
    sta $4304
.endif
    ; Only the 32 used palette colors, not all 256 CGRAM entries.
    stz $2121
    lda #$22
    sta $4301
    ldx #$5400
    stx $4302
    ldx #32
    stx $4305
    lda #1
    sta $420B
    .repeat 4, palette
        lda #$80+palette*16
        sta $2121
        ldx #$5500+palette*32
        stx $4302
        ldx #8
        stx $4305
        lda #1
        sta $420B
    .endrepeat
.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA
    stz $1CED
@final_registers:
.endif
    lda $1C20
    and #2
    asl
    asl
    ora #$21                ; 64x32: adjacent NES nametables, not 32-tile wrap
    sta $2107
    lda $1C28
    sta $210D
    lda $1C20
    and #1
    sta $210D              ; nametable X select is scroll bit 8
    rep #$20
    .a16
    lda $1C29
    and #$00FF
    dec
    sta $08
    sep #$20
    .a8
    lda $08
    sta $210E
    lda $09
    sta $210E              ; preserve existing NES/SNES -1-line alignment
    ; RCR uses three horizontal bands: HUD, scrolling street, lower text.
    ; HDMA applies their scroll values at scanline boundaries independently
    ; of CPU game/audio service. Tables are rebuilt only during VBlank.
    stz $420C
    lda $0100
    and #$C0
    cmp #$C0
    bne @no_split
    lda #32
    sta $1C90
    lda a:$00DE
    sta $1C91
    stz $1C92
    lda #127
    sta $1C93
    lda #35
    sta $1C96
    lda a:$00F6
    sta $1C94
    sta $1C97
    lda a:$003D
    and #1
    sta $1C95
    sta $1C98
    lda #45
    sta $1C99
    lda a:$00DF
    sta $1C9A
    stz $1C9B
    stz $1C9C
    lda #2                 ; HDMA mode 2: two writes to BG1HOFS
    sta $4310
    lda #$0D
    sta $4311
    ldx #$1C90
    stx $4312
    lda #$7E
    sta $4314
    lda #2
    sta $420C
@no_split:
    ; NES PPUMASK bits 1/2 independently expose the leftmost eight BG/OBJ
    ; pixels. Window 1 masks exactly x=0..7 on the main screen.
    stz $2126
    lda #7
    sta $2127
    lda #$11
    sta $212E
    lda $1C21
    and #2
    eor #2
    sta $2123
    lda $1C21
    and #4
    lsr
    eor #2
    sta $2125
    lda $1C21
    and #8
    lsr
    lsr
    lsr
    sta $08
    lda $1C21
    and #$10
    ora $08
    pha
    lda $1CA0
    beq @show_layers
    pla
    lda #0
    bra @set_layers
@show_layers:
    pla
@set_layers:
    sta $212C
    lda #$0F
    sta $2100
    ; Hardware assertion: consumer must not extend past VBlank.
    lda $2137
    lda $213D
    sta $1C7E
    lda $213D
    and #1
    sta $1C7F
.ifdef EXPERIMENTAL_TRANSITION_PREPARE_DEFER
    ; State 1/2 work ran under forced blank, where VRAM DMA is legal outside
    ; VBlank. Once transition_ready clears state 2, assert visible timing.
    lda $1CA0
    bne :+
.endif
    lda $4212
    bmi :+
    lda #1
    sta $1C7B
    lda $1C7E
    sta $1C68
    lda $1C7F
    sta $1C69
    lda $1C7C
    sta $1C6A
:
    rts

.ifdef EXPERIMENTAL_HIDDEN_ROW_RUN
prepare_row_dma_run:
    .a8
    lda $1CA0
    cmp #2
    beq :+
    jmp pair_ready_row
:
    jmp ready_row_run
advance_ready_rows:
    .a16
    lda $1E
    .repeat 6
        lsr
    .endrepeat
    dec
    sta $08
    txa
    clc
    adc $08
    tax
    rts
ready_row_run:
    ; Forced-blank only. Collect a contiguous immutable run within the
    ; existing byte budget, never across row 127. Retire every additional
    ; row exactly as pair_ready_row does; the caller owns the first row.
    .a8
    lda #64
    sta $1E
    stz $1F
    phx
@next:
    inx
    cpx #128
    bcs @done
    rep #$20
    .a16
    lda $1E
    clc
    adc #64
    cmp $1A
    sep #$20
    .a8
    bcc @fits
    bne @done
@fits:
    lda $1D00,x
    and #2
    beq @done
    lda $1D00,x
    and #1
    sta $1D00,x
    beq :+
    sta $1C85
:
    lda $1E80,x
    beq :+
    dec $1E80,x
:
    rep #$20
    .a16
    lda $1E
    clc
    adc #64
    sta $1E
    sep #$20
    .a8
    bra @next
@done:
    plx
    rts
.endif
pair_ready_row:
    ; Two adjacent immutable rows occupy one contiguous staging/VRAM span.
    ; Never cross the queue boundary or merge an unprepared next row.
    .a8
    lda #64
    sta $1E
    stz $1F
    cpx #127
    beq @done
    rep #$20
    .a16
    lda $1A
    cmp #128
    sep #$20
    .a8
    bcc @done
    lda $1D01,x
    and #2
    beq @done
    lda #128
    sta $1E
    lda $1D01,x
    and #1
    sta $1D01,x
    beq :+
    sta $1C85
:
    lda $1E81,x
    beq @done
    dec $1E81,x
@done:
    rts

dma_room:
    lda $1CA0
    bne @blank
    ; A8, X/Y preserved. NTSC 239-line display: VBlank ends at scanline 262.
    ; Refuse CHR DMA after line 242, reserving the rest of VBlank for this
    ; whole-bank transfer and the final OAM/palette batch.
    lda $4212
    bpl @no
    lda $2137
    lda $213D
    sta $1C
    lda $213D
    and #1
    bne @no
    lda $1C
    cmp #243
    bcs @no
@blank:
    sec
    rts
@no:
    clc
    rts

final_room:
    .a8
    lda $4212
    bpl @no
    lda $2137
    lda $213D
    sta $1C
    lda $213D
    and #1
    bne @no
    lda $1C
    cmp #250
    bcs @no
    sec
    rts
@no:
    clc
    rts

.ifdef EXPERIMENTAL_PLANAR_ROWS
    .include "planar_dma.inc"
.endif
transition_ready:
    .a8
    lda $1CA0
    cmp #2
    beq :+
    rts
:
    lda $1C21
    and #$18
    bne :+
    rts
:
    ; Called before the final-batch timing check. Work is bounded, and only
    ; applies to an explicit off->on transition, never routine scrolling.
    rep #$20
    .a16
    lda $1E80
    .repeat 63, pair
        ora $1E82+pair*2
    .endrepeat
    .repeat 12, pair
        ora $1D80+pair*2
    .endrepeat
    sep #$20
    .a8
    bne @return
.ifdef EXPERIMENTAL_TRANSITION_GAME_FIRST
    ; A post-game drain may run under forced blank during active display.
    ; Latch readiness and let the next hardware VBlank expose the layers.
    lda $4212
    bmi @finish_transition
    lda #1
    sta $1CEF
    rts
@finish_transition:
    stz $1CEF
.endif
    stz $1CA0
.ifdef EXPERIMENTAL_TRANSITION_WAIT_PREPARE
    ; A final split opportunity is obsolete once every required row/CHR job
    ; has drained and the layers are ready to become visible.
    stz $1CF0
.endif
@return:
    rts

row_room:
    .a8
    lda $1CA0
    bne @blank
    lda $4212
    bpl @no
    lda $2137
    lda $213D
    sta $1C
    lda $213D
    and #1
    bne @no
    lda $1C
    cmp #246
    bcs @no
@blank:
    sec
    rts
@no:
    clc
    rts
