; Bank-replicated E=1 runtime. DB always mirrors the active HiROM bank ($81-$88).
; Hook ABI: $1B20/21 = effective address, $1B22 = write data, $1B24 = read result.
; Trace-covered game PPU/APU writes and MMC3 paired PRG switching.
; Bootstrap publishes graphics/audio; raster IRQ and full mapper fidelity remain open.
.setcpu "65816"
.a8
.i8
.include "apu_length_gate.inc"
.include "interrupt_policy.inc"
.include "early_audio_abi.inc"
.ifdef EXPERIMENTAL_EARLY_DEFERRED_AUDIO
    .include "early_gameplay_audio.asm"
.endif
.segment "CODE"
.ifdef EXPERIMENTAL_SWEEP_EVENTS
    .include "sweep_events.inc"
.endif
.ifdef EXPERIMENTAL_BANK_RESTORE
    .include "bank_restore.inc"
.endif
.ifdef EXPERIMENTAL_DIRECT_APU
    .include "direct_apu.inc"
.endif
.ifdef EXPERIMENTAL_SOUND_COMMIT
    .include "sound_commit.inc"
.endif
.ifdef EXPERIMENTAL_PALETTE_COPY
    .include "palette_copy.inc"
.endif
dispatch_write:
.ifdef TRACE_CALLERS
    jsr trace_caller
.endif
    php
    pha
    phx
    phy
    phd
    stz $4200
    lda #$1B
    xba
    lda #0
    tcd
    lda $21
    cmp #$20
    bne :+
    jmp ppu_write
:
    cmp #$40
.ifdef EXPERIMENTAL_CHR_DIRTY_GATE
    bne :+
    jmp console_write
:
    cmp #$80
    bne :+
    jmp mapper_write
:
.else
    beq console_write
    cmp #$80
    beq mapper_write
.endif
    cmp #$A0
    beq mirror_write
    cmp #$C0
    beq mapper_irq
    cmp #$E0
    beq mapper_irq
    inc a:$1C06
    jmp done
mirror_write:
    lda $20
    and #1
    bne @done             ; $A001 is PRG-RAM protection, not mirroring
    lda $22
    and #1
    cmp a:$1C18
    beq @done
    sta a:$1C18
    ldx #127
    lda #1
@invalidate:
    sta a:$1D00,x
    dex
    bpl @invalidate
    sta a:$1C85
@done:
    jmp done
mapper_irq:
    ; Store IRQ register activity for the later timing adapter; do not pretend
    ; this CPU proof implements scanline splits.
    inc a:$1C07
    jmp done
mapper_write:
.ifdef EXPERIMENTAL_CHR_READ_CACHE
    ; Private one-page CHR read-pointer cache. Any mapper transaction makes
    ; the next read resolve afresh, including selector inversion changes.
    stz a:$1B50
.endif
    lda $20
    and #1
    bne @data
    lda $22
.ifdef EXPERIMENTAL_CHR_DIRTY_GATE
    pha
    eor a:$1C19
    and #$80
    beq :+
    lda #1
    sta a:$1CBB
:
    pla
.endif
    sta a:$1C19
    jmp done
@data:
    lda a:$1C19
    and #7
    tax
    lda $22
    sta a:$1C10,x          ; R0..R7 start at $1C10; selection has separate byte below
    cpx #7
    bne @chr
    lda a:$1C16
    and #$0F
    lsr
    clc
    adc #$C1
    sta a:$1C03
    sta a:$1C02
    jmp done_banked
@chr:
.ifdef EXPERIMENTAL_CHR_DIRTY_GATE
    cpx #6
    bcs :+
    lda #1
    sta a:$1CBB
:
.endif
    inc a:$1C08
    jmp done
console_write:
    lda $20
    cmp #$14
    bne :+
    jmp @dma
:
    cmp #$16
    beq @joy
    cmp #$18
    bcs @end
    tax
    lda $22
    sta a:$0A00,x
    jsr apu_length_write
.ifdef EXPERIMENTAL_SWEEP_EVENTS
    jsr sweep_track_write
.endif
    ; Legacy SPC bits 6/7 reload the pulse period used by sweep. Track
    ; actual timer writes (including zero), not whether the value changed.
    txa
    and #$FE
    cmp #2
    beq @reload_pulse0
    cmp #6
    bne @note_flags
    lda #$80
    bra @reload_pulse
@reload_pulse0:
    lda #$40
@reload_pulse:
    ora a:$0A16
    sta a:$0A16
@note_flags:
    txa
    and #3
    cmp #3
    bne @end
    txa
    cmp #$10
    bcs @end
    lsr
    lsr
    tay
    lda #1
@retrigger:
    cpy #0
    beq @flag
    asl
    dey
    bra @retrigger
@flag:
    ora a:$0A16
    sta a:$0A16
@end:
    jmp done
@joy:
    lda $22
    and #1
    sta $4016
    tax
    lda a:$1C82
    stx a:$1C82
.ifdef EXPERIMENTAL_CONTROL_PRESETS
    cpx #0
    beq :+
    jmp @joy_done
:
    and #1
    bne :+
    jmp @joy_done
:
.else
    cpx #0
    bne @joy_done
    and #1
    beq @joy_done
.endif
    ; Falling strobe: latch both SNES pads. First eight bits retain the
    ; NES B/Y/Select/Start/direction mapping; ninth bit is SNES A (jump).
    ldy #8
@buttons:
    lda $4016
    lsr
    ror a:$1C80
    lda $4017
    lsr
    ror a:$1C81
    dey
    bne @buttons
.ifdef EXPERIMENTAL_CONTROL_PRESETS
    ; First two serial bits are physical B,Y. Collect A,X too, then remap
    ; each pad to the NES A/B bits. Select/Start/directions remain untouched.
    lda a:$1C80
    and #3
    sta a:$1CFB
    lda a:$1C81
    and #3
    sta a:$1CFC
    lda $4016              ; ninth bit: SNES A
    and #1
    beq :+
    lda a:$1CFB
    ora #4
    sta a:$1CFB
:
    lda $4017
    and #1
    beq :+
    lda a:$1CFC
    ora #4
    sta a:$1CFC
:
    lda $4016              ; tenth bit: SNES X
    and #1
    beq :+
    lda a:$1CFB
    ora #8
    sta a:$1CFB
:
    lda $4017
    and #1
    beq :+
    lda a:$1CFC
    ora #8
    sta a:$1CFC
:
    lda $4016              ; L/R change presets in the pregame settings
    and #1
    sta a:$1CFA
    lda $4016
    and #1
    asl
    ora a:$1CFA
    sta a:$1CFA
    lda a:$1CF9
    eor #3
    and a:$1CFA
    sta $04
    lda a:$1CFA
    sta a:$1CF9
    lda a:$0006
    cmp #5                 ; original settings task, not gameplay/pause
    bne @map_pads
    lda a:$010B
    cmp #1
    bne @map_pads
    lda a:$0519
    bne @map_pads
    lda $04
    and #2
    beq :+
    lda a:$1CF8
    inc
    and #3
    sta a:$1CF8
    bra @map_pads
:
    lda $04
    and #1
    beq @map_pads
    lda a:$1CF8
    dec
    and #3
    sta a:$1CF8
@map_pads:
    lda a:$1CF8
    asl
    asl
    asl
    asl
    ora a:$1CFB
    tax
    lda f:control_input_table,x
    sta $04
    lda a:$1C80
    and #$FC
    ora $04
    sta a:$1C80
    lda a:$1CF8
    asl
    asl
    asl
    asl
    ora a:$1CFC
    tax
    lda f:control_input_table,x
    sta $04
    lda a:$1C81
    and #$FC
    ora $04
    sta a:$1C81
.else
    lda $4016
    and #1
    beq :+
    lda a:$1C80
    ora #3
    sta a:$1C80
:
    lda $4017
    and #1
    beq @joy_done
    lda a:$1C81
    ora #3
    sta a:$1C81
.endif
@joy_done:
    jmp done
@dma:
    ; NES OAM DMA is a page copy in low WRAM. Native block move avoids
    ; 256 indirect-load/store loop iterations; NMI is already masked.
    phb
    clc
    xce
    rep #$30
    .a16
    .i16
    lda $22
    and #$00FF
.ifdef EXPERIMENTAL_OAM_WORD_COPY
    ; Bank-zero direct page maps WRAM only below $2000. Preserve the existing
    ; explicit-WRAM MVN path for all other pages. Page-aligned DP avoids the
    ; misaligned-D penalty; 16-bit loads/stores retain exact snapshot bytes.
    cmp #$20
    bcc :+
    jmp @dma_mvn
:
    xba
    tcd
    .repeat 128, word
        lda z:word*2
        sta f:$7E1000 + word*2
    .endrepeat
    jmp @dma_copied
@dma_mvn:
.endif
    xba
    tax
    ldy #$1000
    lda #255
    mvn $7E0000,$7E0000     ; ca65 derives bank operands from full addresses
@dma_copied:
.ifdef EXPERIMENTAL_OAM_DIRTY_GATE
    sep #$20
    .a8
    lda #1
    sta a:$1C87
    rep #$20
    .a16
.endif
    sep #$30
    .a8
    .i8
    sec
    xce
    plb
    jmp done
dispatch_ppudata:
.ifdef TRACE_CALLERS
    jsr trace_caller
.endif
    ; STA $2007 has a known destination: only the data mailbox is needed.
    ; Keep the same saved-register and non-reentrant shadow-write ABI.
    php
    pha
    phx
    phy
    phd
    stz $4200
    lda #$1B
    xba
    lda #0
    tcd
    jmp ppu_write_data
ppu_write:
    lda $20
    and #7
    tax
    lda $22
    cpx #0
    beq @ctrl
    cpx #1
    beq @mask
    cpx #3
    bne :+
    jmp @oamaddr
:
    cpx #4
    bne :+
    jmp @oamdata
:
    cpx #5
    bne :+
    jmp @scroll
:
    cpx #6
    bne :+
    jmp @addr
:
    cpx #7
    bne :+
    jmp @data
:
    jmp done
@ctrl:
.ifdef EXPERIMENTAL_CHR_DIRTY_GATE
    pha
    eor a:$1C20
    and #$18
    beq :+
    lda #1
    sta a:$1CBB
:
    pla
.endif
    sta a:$1C20
    jmp done
@mask:
    sta a:$1C21
    and #$18
    bne @render_on
    ; Honor rendering-off even during a long NMI-disabled load.
    stz $212C
    lda #1
    sta a:$1CA0
    ; The display is already blank. Preserve dirtiness for the next normal
    ; producer or render-on write instead of converting an unfinished load.
    jmp done
@render_on:
    lda a:$1CA0
    cmp #1
    bne @mask_schedule
    lda a:$1C20
    eor a:$1C78
    and #$10
    sta $05
    ldx #0
@snapshot_rows:
    txa
    and #31
    cmp #30
    bcc @visible_row
    lda #0
    bra @initial_row
@visible_row:
    lda $05
    bne @rebuild_row
    lda a:$1D00,x
    cmp #3
    bne @initial_row
@rebuild_row:
    lda #1
    ; Discard stale staged data only when a newer shadow exists, or the
    ; pattern-table selection changes. Clean and current staged rows survive.
@initial_row:
    sta a:$1D00,x
    cmp #0
    beq @row_requirement
    lda #1
@row_requirement:
    sta a:$1E80,x
    inx
    cpx #128
    bne @snapshot_rows
    lda #1
    sta a:$1C85
    lda #2
    sta a:$1CA0
@mask_schedule:
    ; Both original-NMI exit adapters prepare graphics after game updates.
    ; Do not run the same expensive producer early inside that interrupt.
    lda a:$1C0A
    bne @mask_done
    ; With a running NMI pipeline, the next exit prepares the updated shadow.
    ; Keep synchronous preparation for initial setup and NMI-disabled loads.
    lda a:$1C79
    beq @prepare_mask
    lda a:$1C20
    bmi @mask_done
@prepare_mask:
    jsl $C00000+video_prepare_bridge
@mask_done:
    jmp done
@oamaddr:
    sta a:$1C23
    jmp done
@oamdata:
    ldx a:$1C23
    sta a:$1000,x
.ifdef EXPERIMENTAL_OAM_DIRTY_GATE
    pha
    lda #1
    sta a:$1C87
    pla
.endif
    inc a:$1C23
    jmp done
@scroll:
    ldx a:$1C25
    sta a:$1C28,x
    txa
    eor #1
    sta a:$1C25
    jmp done
@addr:
    ldx a:$1C25
    bne @low
    and #$3F
    sta a:$1C27
    lda #1
    sta a:$1C25
    jmp done
@low:
    sta a:$1C26
    stz a:$1C25
    jmp done
@data:
ppu_write_data:
    jsr ppu_pointer
    lda $22
    ; Preserve every existing publication state for an identical shadow byte;
    ; increments and write accounting remain unconditional.
    cmp [$00]
    beq @unchanged
    sta [$00]
    jsr mark_ppu_dirty
@unchanged:
    jsr ppu_increment
    inc a:$1C09
    jmp done

mark_ppu_dirty:
    lda a:$1C27
    cmp #$20
    bcc @end
    cmp #$3F
    bcs @end
    pha
    lda #1
    sta a:$1C85
    pla
    and #3
    cmp #3
    bne @tile
    lda a:$1C26
    cmp #$C0
    bcc @tile
    and #$38
    lsr
    sta $04
    lda a:$1C27
    and #$0C
    asl
    asl
    asl
    ora $04
    tax
    jsr dirty_mirrored_row
    inx
    jsr dirty_mirrored_row
    inx
    jsr dirty_mirrored_row
    inx
    jsr dirty_mirrored_row
    rts
@tile:
    lda a:$1C27
    and #$0F
    asl
    asl
    asl
    sta $04
    lda a:$1C26
    lsr
    lsr
    lsr
    lsr
    lsr
    ora $04
    tax
    jsr dirty_mirrored_row
@end:
    rts

dirty_mirrored_row:
    lda a:$1D00,x
    ora #1
    sta a:$1D00,x
    phx
    lda a:$1C18
    and #1
    beq @vertical
    txa
    eor #$20
    bra @alias
@vertical:
    txa
    eor #$40
@alias:
    tax
    lda a:$1D00,x
    ora #1
    sta a:$1D00,x
    plx
    rts

dispatch_ppudata_read:
.ifdef TRACE_CALLERS
    jsr trace_caller
.endif
    php
    pha
    phx
    phy
    phd
    stz $4200
    lda #$1B
    xba
    lda #0
    tcd
    jmp ppu_read_data
dispatch_read:
.ifdef TRACE_CALLERS
    jsr trace_caller
.endif
    php
    pha
    phx
    phy
    phd
    stz $4200
    lda #$1B
    xba
    lda #0
    tcd
    stz $24
    lda $21
    cmp #$20
    beq @ppu
    cmp #$40
    bne @unknown
    lda $20
    cmp #$16
    beq @joy1
    cmp #$17
    beq @joy2
    jmp done
@joy1:
    lda a:$1C82
    bne @live1
    lda a:$1C80
    sec
    ror a:$1C80
    bra @bit1
@live1:
    lda $4016
@bit1:
    and #1
    sta $24
    jmp done
@joy2:
    lda a:$1C82
    bne @live2
    lda a:$1C81
    sec
    ror a:$1C81
    bra @bit2
@live2:
    lda $4017
@bit2:
    and #1
    sta $24
    jmp done
@unknown:
    inc a:$1C06
    jmp done
@ppu:
    lda $20
    and #7
    cmp #2
    beq @status
    cmp #7
    beq @data
    jmp done
@status:
    stz a:$1C25
    lda $4212
    and #$80
    sta $24
    jmp done
@data:
ppu_read_data:
    jsr ppu_read_buffer
    jmp done
ppu_read_buffer:
    jsr ppu_pointer
    lda a:$1C2A
    sta $24
    jsr chr_read_pointer
    lda [$00]
    sta a:$1C2A
    lda a:$1C27
    cmp #$3F
    bcc :+
    lda a:$1C2A
    sta $24
    ; Palette data bypasses the read buffer, but the same read refills that
    ; buffer from the nametable underneath, using the unaliased low address.
    lda a:$1C26
    sta $00
    lda #$2F
    sta $01
    jsr nametable_pointer
    lda [$00]
    sta a:$1C2A
:
    jsr ppu_increment
    rts

ppu_pointer:
    lda a:$1C26
    sta $00
    lda #$7F
    sta $02
    lda a:$1C27
    and #$3F
    sta $01
    cmp #$3F
    beq @palette
    cmp #$20
    bcc @shadow_bank
    bra nametable_pointer
@palette:
    ; Palette RAM repeats every 32 bytes; sprite transparent entries alias
    ; the corresponding background entries ($10/$14/$18/$1C -> $00/04/08/0C).
    lda $00
    and #$1F
    sta $00
    and #3
    bne @shadow_bank
    lda $00
    and #$0F
    sta $00
@shadow_bank:
    rts
nametable_pointer:
    ; $2000/$2400 back the two persistent physical 1KiB CIRAM tables.
    ; $3000 mirrors $2000. Preserve offset bits and select physical bit 10.
    lda a:$1C18
    and #1
    bne @horizontal
    lda $01
    and #$27
    sta $01
    rts
@horizontal:
    lda $01
    and #3
    ora #$20
    sta $03
    lda $01
    lsr
    and #4
    ora $03
    sta $01
    rts
chr_read_pointer:
.ifdef EXPERIMENTAL_CHR_READ_CACHE
    ; Only the pointer is the internal ABI here. Both callers discard X and
    ; resolver scratch $03/$04; public read helpers still preserve their own
    ; caller ABI. Do not reuse a binary mapping for a decimal-mode caller.
    lda a:$1C27
    cmp #$20
    bcs chr_cache_done
    php
    pla
    and #8
    bne chr_cache_uncached
    jsr chr_cache_validate
    lda a:$1B55
    sta $01
    lda a:$1B56
    sta $02
chr_cache_done:
    rts
chr_cache_uncached:
    jmp chr_read_pointer_uncached
chr_cache_validate:
    ; Internal entry only: caller has already proved D=0 and PPUADDR<$2000.
    ; Still validate page identity and mapper invalidation on every call.
    ; $1B54..56 is a persistent long pointer, with its low byte supplied by
    ; the paired caller. Generic reads copy high/bank into their own pointer.
    lda a:$1C27
    cmp a:$1B51
    bne chr_cache_resolve
    lda a:$1B50
    beq chr_cache_resolve
    rts
chr_cache_resolve:
    jsr chr_read_pointer_uncached
    lda a:$1C27
    sta a:$1B51
    lda $01
    sta a:$1B55
    lda $02
    sta a:$1B56
    lda #1
    sta a:$1B50
    rts
chr_read_pointer_uncached:
.endif
    ; RCR also stores nametable data in CHR ROM and reads it through PPUDATA.
    lda a:$1C27
    cmp #$20
    bcs @done
    lsr
    lsr
    sta $03
    lda a:$1C19
    and #$80
    beq :+
    lda $03
    eor #4
    sta $03
:
    lda $03
    cmp #4
    bcs @single
    lsr
    tax
    lda a:$1C10,x
    and #$FE
    sta $04
    lda $03
    and #1
    ora $04
    bra @bank
@single:
    sec
    sbc #2
    tax
    lda a:$1C10,x
@bank:
    and #$7F
    ; bank * 1024: two shifts give the pointer high byte and carry is
    ; original bank bit 6, selecting CF/D0. STA/LDA preserve that carry.
    asl
    asl
    sta $01
    lda #$CF
    adc #0
    sta $02
    lda a:$1C27
    and #3
    ora $01
    sta $01
@done:
    rts
.ifdef TRACE_CALLERS
trace_caller:
    ; JSR here adds two bytes to the hook's JSL/PHP/PHA/JSR frame.
    php
    pha
    phx
    tsx
    .repeat 11
        inx
    .endrepeat
    lda $0100,x
    sta a:$1C30
    inx
    lda $0100,x
    sta a:$1C31
    plx
    pla
    plp
    rts
.endif
ppu_increment:
    lda a:$1C20
    and #4
    beq @one
    lda #32
    bra @add
@one:
    lda #1
@add:
    clc
    adc a:$1C26
    sta a:$1C26
    bcc :+
    inc a:$1C27
:
    rts
done:
    ; Ordinary PPU/APU/controller accesses do not change the program bank.
    ; Their original JSL return bank and DB are already correct.
    pld
    ply
    plx
    pla
    plp
    rtl
done_banked:
    pld
    ply
    plx
    pla
    plp
    ; Bank writes can change the active PRG pair. Replace this JSL's return
    ; bank on the emulation stack; all stubs/helpers are duplicated in each bank.
    php
    pha
    phx
    lda a:$1C03
    tsx
    inx
    inx
    inx
    inx
    inx
    inx
    sta $0100,x
    and #$3F
    ora #$80
    pha
    plb
    plx
    pla
    plp
    rtl

; Fixed-bank C90C writes one decompressed byte after two PPUADDR writes.
; Translate the complete helper with one guarded adapter-DP interval instead
; of separate full I/O transactions. Preserve a half-written PPUADDR latch.
bulk_ppu_byte:
    stz $4200
    lda a:$1C25
    bne @swapped
    lda $2D
    and #$3F
    sta a:$1C27
    lda $2C
    sta a:$1C26
    bra @write
@swapped:
    lda $2D
    sta a:$1C26
    lda $2C
    and #$3F
    sta a:$1C27
@write:
    lda $1B
    sta a:$1B22
    phx
    phd
    lda #$1B
    xba
    lda #0
    tcd
    jsr ppu_pointer
    lda $22
    ; A decompressed byte equal to its physical shadow needs no new row
    ; publication. Existing dirty/staged flags remain untouched. Address
    ; increment and write accounting below still run for every NES write.
    cmp [$00]
    beq @unchanged
    sta [$00]
    jsr mark_ppu_dirty
@unchanged:
    jsr ppu_increment
    inc a:$1C09
    pld
    plx
    lda a:$1C0A
    ora a:$1C83
    bne @increment
    load_interrupt_enable
    beq @increment
    sta $4200
@increment:
    ; Original final A/N/Z/C and source pointer update, independent of the
    ; PPUCTRL increment (which ppu_increment already applied).
    clc
    lda $2C
    adc #1
    sta $2C
    lda $2D
    adc #0
    sta $2D
    rts

; C88F width-one rectangular runs: flatten the outer loop while NMI is off.
; Keep the original nested loop for all unsupported states/dimensions.
bulk_rect_loop:
    jsr bulk_rect_bytes
    jmp $C89B
bulk_repeat_loop:
    jsr bulk_repeat_bytes
    jmp $C867
bulk_repeat_bytes:
    ; Borrow the rectangular engine only with NMI disabled. Its temporary
    ; width/height must not be observable to an interrupting game update.
    lda a:$1C20
    and #$80
    bne @fallback
    lda $1C
    pha
    lda $1D
    pha
    stx $1C
    lda #1
    sta $1D
    jsr bulk_rect_bytes
    sta a:$1B1A
    php
    pla
    sta a:$1B1B
    pla
    sta $1D
    pla
    sta $1C
    lda a:$1B1B
    pha
    lda a:$1B1A
    plp
    rts
@fallback:
    jsr bulk_ppu_byte
    dex
    bne @fallback
    rts
bulk_rect_bytes:
    lda $1D
    cmp #1
    beq :+
    jmp @fallback
:
    lda a:$1C25
    beq :+
    jmp @fallback
:
    lda a:$1C20
    and #$84
    beq :+
    jmp @fallback
:
    lda $2D
    cmp #$20
    bcs :+
    jmp @fallback
:
    cmp #$2F
    bcc :+
    jmp @fallback
:
    php
    pla
    and #8
    beq :+
    jmp @fallback
:
    stz $4200
    lda $1C
    sta a:$1B18
    stz a:$1B19
.ifdef EXPERIMENTAL_RECT_DMA
    lda $1C
    bne :+
    inc a:$1B19            ; original zero counter means a 256-byte run
:
.endif
    lda $2C
    sta a:$1C26
    lda $2D
    sta a:$1C27
    lda $1B
    sta a:$1B22
    phd
    lda #$1B
    xba
    lda #0
    tcd
    jsr ppu_pointer
.ifdef EXPERIMENTAL_RECT_DMA
    ; The guarded run is a constant-byte fill with NMI already masked.  Check
    ; and mark each eight-byte logical segment, then block-fill the shadow.
    ; Split at each logical page boundary so nametable mirroring is resolved
    ; again before the next physical chunk.
    lda a:$1C26
    sta $08
    lda a:$1C27
    sta $09
    phy
    lda $18
    sta $06
    lda $19
    sta $07
@dma_mark:
    lda a:$1C26
    and #7
    eor #7
    inc
    sta $0A
    stz $0B
    lda $07
    bne @dma_mark_step
    lda $06
    cmp $0A
    bcs @dma_mark_step
    sta $0A
@dma_mark_step:
    ; Preserve the unchanged-byte fast path: only a segment containing at
    ; least one different physical shadow byte becomes dirty.
    ldy #0
@dma_compare:
    lda [$00],y
    cmp $22
    bne @dma_changed
    iny
    cpy $0A
    bne @dma_compare
    bra @dma_advance_mark
@dma_changed:
    jsr mark_ppu_dirty
@dma_advance_mark:
    lda a:$1C26
    clc
    adc $0A
    sta a:$1C26
    bcc @dma_mark_same_page
    inc a:$1C27
    jsr ppu_pointer
    bra @dma_mark_subtract
@dma_mark_same_page:
    lda $00
    clc
    adc $0A
    sta $00
@dma_mark_subtract:
    lda $06
    sec
    sbc $0A
    sta $06
    lda $07
    sbc #0
    sta $07
    ora $06
    beq :+
    jmp @dma_mark
:
    lda $08
    sta a:$1C26
    lda $09
    sta a:$1C27
    jsr ppu_pointer
@dma_chunk:
    ; Chunk length is min(remaining, 256 - logical low address).  A zero low
    ; byte with high byte one represents the full 256-byte page, never the
    ; SNES DMA controller's special 65536-byte zero length.
    lda $19
    bne @dma_to_page
    lda $18
    clc
    adc a:$1C26
    bcc @dma_all_remaining
@dma_to_page:
    lda #0
    sec
    sbc a:$1C26
    sta $04
    stz $05
    bne @dma_start
    inc $05
    bra @dma_start
@dma_all_remaining:
    lda $18
    sta $04
    stz $05
@dma_start:
    ; Seed the first byte and copy it forward over itself.  MVN increments
    ; source and destination after every byte, so destination=source+1 turns
    ; one dynamic byte into a constant fill without an illegal WRAM-to-WRAM
    ; DMA.  The count is chunk-2 because the seed is already present.
    lda $22
    sta [$00]
    lda $05
    bne @dma_copy_rest
    lda $04
    cmp #1
    beq @dma_advance
@dma_copy_rest:
    clc
    xce
    rep #$30
    .a16
    .i16
    lda $04
    dec
    dec
    ldx $00
    ldy $00
    iny
    phb
    mvn $7F0000,$7F0000
    plb
    sep #$30
    .a8
    .i8
    sec
    xce
@dma_advance:
    ; Advance the logical PPU address and remaining byte count as words.
    clc
    xce
    rep #$20
    .a16
    lda a:$1C26
    clc
    adc $04
    sta a:$1C26
    lda $18
    sec
    sbc $04
    sta $18
    sep #$20
    .a8
    sec
    xce
    lda $18
    ora $19
    beq @dma_done
    jsr ppu_pointer
    bra @dma_chunk
@dma_done:
    ply
    pld
    lda a:$1C09
    clc
    adc $1C                ; zero height means 256, so modulo-256 add is zero
    sta a:$1C09
    lda a:$1C26
    sta $2C
    lda a:$1C27
    sta $2D
    stz $1C
    clc
    clv
    ldx #0
    rts
.endif
@byte:
    lda $22
    cmp [$00]
    beq @same
    sta [$00]
    lda $19
    bne @same
    jsr mark_ppu_dirty
    lda #1
    sta $19
@same:
    inc a:$1C09
    inc a:$1C26
    bne @same_page
    inc a:$1C27
    jsr ppu_pointer
    bra @segment
@same_page:
    inc $00
@segment:
    lda a:$1C26
    and #7
    bne :+
    stz $19
:
    dec $18
    bne @byte
    pld
    lda a:$1C26
    sta $2C
    lda a:$1C27
    sta $2D
    stz $1C
    clc
    clv
    ldx #0
    rts
@fallback:
    ldx $1D
@fallback_byte:
    jsr bulk_ppu_byte
    dex
    bne @fallback_byte
    dec $1C
    bne @fallback
    rts

; C872 literal command: cache source and destination pointers within pages.
; Other modes and all boundary cases retain the original helper loop.
bulk_literal_loop:
    jsr bulk_literal_bytes
    jmp $C87B
bulk_literal_bytes:
    cpx #0
    beq @fallback
    cpx #64
    bcs @fallback
    lda a:$1C20
    and #$84
    bne @fallback
    lda a:$1C25
    bne @fallback
    php
    pla
    and #8
    bne @fallback
    lda $2B
    cmp #$20
    bcs @fallback
    lda $2D
    cmp #$20
    bcc @fallback
    cmp #$2F
    bcs @fallback
    txa
    clc
    adc $1A
    bcs @fallback          ; source-index wrap changes base-address addition
    lda $2A
    clc
    adc $1A
    bcs @fallback          ; constrain source + lookahead to one mapped page
    sta a:$1B08
    txa
    adc a:$1B08
    bcs @fallback
    txa
    clc
    adc $2C
    bcc :+
@fallback:
    jsr bulk_source_byte
    jsr bulk_ppu_byte
    dex
    bne @fallback
    rts
:
    stz $4200
    stx a:$1B18
    stz a:$1B19
    lda a:$1B08
    sta a:$1C26
    lda $2B
    sta a:$1C27
    phd
    lda #$1B
    xba
    lda #0
    tcd
    jsr ppu_pointer
    jsr chr_read_pointer
    lda $00
    sta $08
    lda $01
    sta $09
    lda $02
    sta $0A
    lda a:$002C
    sta a:$1C26
    lda a:$002D
    sta a:$1C27
    jsr ppu_pointer
@byte:
    lda [$08]
    sta a:$001B
    sta $22
    cmp [$00]
    beq @same
    sta [$00]
    lda $19
    bne @same
    jsr mark_ppu_dirty
    lda #1
    sta $19
@same:
    inc $08
    inc a:$001A
    inc $00
    inc a:$1C26
    inc a:$1C09
    lda a:$1C26
    and #7
    bne :+
    stz $19
:
    dec $18
    bne @byte
    ; No game NMI can observe intermediate read-buffer values. Only the
    ; last source read's lookahead survives this complete literal command.
    lda [$08]
    sta a:$1C2A
    lda $22
    sta $24               ; retain the final source-reader mailbox value
    pld
    lda $1A
    dec
    clc
    adc $2A
    sta $2E
    lda $2B
    sta $2F
    lda a:$1C26
    sta $2C
    lda $2D
    clc
    clv
    ldx #0
    rts

; FCF7: constant attribute fill. Batch only the checked 64-byte, aligned,
; increment-one, NMI-disabled case; other states retain per-byte dispatch.
bulk_attribute_loop:
    jsr bulk_attribute_bytes
    jmp $FCFD
bulk_attribute_bytes:
    php
    pha
    cpx #$40
    bne @fallback
    lda a:$1C20
    and #$84
    bne @fallback
    lda a:$1C25
    bne @fallback
    lda a:$1C26
    cmp #$C0
    bne @fallback
    lda a:$1C27
    cmp #$20
    bcc @fallback
    cmp #$2F
    bcs @fallback
    and #3
    cmp #3
    bne @fallback
    php
    pla
    and #8
    bne @fallback
    ; No game NMI can observe these borrowed decompressor variables.
    lda $1B
    pha
    lda $1C
    pha
    lda $1D
    pha
    lda $2C
    pha
    lda $2D
    pha
    tya
    sta $1B
    stx $1C
    lda #1
    sta $1D
    lda a:$1C26
    sta $2C
    lda a:$1C27
    sta $2D
    jsr bulk_rect_bytes
    pla
    sta $2D
    pla
    sta $2C
    pla
    sta $1D
    pla
    sta $1C
    pla
    sta $1B
    bra @done
@fallback:
    stz $4200
    sty a:$1B22
    jsl $C10000+dispatch_ppudata
    lda a:$1C0A
    ora a:$1C83
    bne @next
    load_interrupt_enable
    beq @next
    sta $4200
@next:
    dex
    bne @fallback
@done:
    pla
    plp
    ldx #0                 ; original DEX leaves Z=1/N=0, A/Y/C/V intact
    rts

; Fixed-bank C8DB reads the next compressed byte from PPU or CPU memory.
bulk_source_byte:
    lda $2B
    cmp #$80
.ifdef EXPERIMENTAL_CHR_READ_PAIR
    bcc :+
    jmp @cpu
:
.else
    bcs @cpu
.endif
    lda $1A
    clc
    adc $2A
    sta $2E
    lda $2B
    adc #0
    sta $2F
    stz $4200
    lda a:$1C25
    bne @swapped
    lda $2F
    and #$3F
    sta a:$1C27
    lda $2E
    sta a:$1C26
    bra @read
@swapped:
    lda $2F
    sta a:$1C26
    lda $2E
    and #$3F
    sta a:$1C27
@read:
    ; First read fills the PPU buffer; second returns it (or bypasses it
    ; for palette addresses). Keep both address increments and final buffer.
    ; The whole reader already masks NMI. Enter the shared read primitive
    ; once under the adapter DP instead of saving/restoring the full ABI twice.
    php
    phx
    phd
    lda #$1B
    xba
    lda #0
    tcd
.ifdef EXPERIMENTAL_CHR_READ_PAIR
    ; Both buffered reads run inside this already-masked critical section.
    ; Within a binary, increment-one CHR page, resolve once and retain the
    ; first byte as the result plus the second as the final read buffer.
    php
    pla
    and #8
    bne @ordinary_reads
    lda a:$1C20
    and #4
    bne @ordinary_reads
    lda a:$1C27
    cmp #$20
    bcs @ordinary_reads
    lda a:$1C26
    cmp #$FE
    bcs @ordinary_reads
    ; The guards above exclude nametables/palette and decimal mapping.
    ; Reuse the cache's persistent physical pointer directly. Validation is
    ; shared with generic reads, including every mapper invalidation path.
.ifdef EXPERIMENTAL_CHR_READ_CACHE
    jsr chr_cache_validate
    lda a:$1C26
    sta $54
    lda [$54]
    sta $24
    inc $54
    lda [$54]
.else
    lda a:$1C26
    sta $00
    jsr chr_read_pointer
    lda [$00]
    sta $24
    inc $00
    lda [$00]
.endif
    sta a:$1C2A
    inc a:$1C26
    inc a:$1C26
    bra @read_complete
@ordinary_reads:
.endif
    jsr ppu_read_buffer
    jsr ppu_read_buffer
.ifdef EXPERIMENTAL_CHR_READ_PAIR
@read_complete:
.endif
    pld
    plx
    plp
    ; Consume the shared read mailbox before allowing any pending NMI.
    lda a:$1B24
    sta $1B
    pha
    php
    lda a:$1C0A
    ora a:$1C83
    bne @result
    load_interrupt_enable
    beq @result
    sta $4200
@result:
    plp
    pla
    inc $1A
    rts
@cpu:
    ldy $1A
    lda ($2A),y
    sta $1B
    inc $1A
    rts

; FCD6: aligned page fill. Its checked caller sets PPUADDR low=0 and
; PPUCTRL increment=1. X=0 means 256 pages, as in the original DEX loop.
bulk_fill_loop:
    jsr bulk_fill_pages
    jmp $FCE3
bulk_fill_pages:
    php
    phd
    stz $4200
    lda #$1B
    xba
    lda #0
    tcd
.ifdef EXPERIMENTAL_FILL_DIRTY_BATCH
    ; A complete aligned four-page nametable fill ultimately dirties every
    ; logical row in that table and its mirroring alias.  Record the row base
    ; once so the redundant per-8/per-32-byte dirty calls can be collapsed.
    stz $08
    cpx #4
    bne :+
    lda a:$1C26
    bne :+
    lda a:$1C27
    and #3
    bne :+
    lda a:$1C27
    and #$0C
    asl
    asl
    asl
    sta $09
    lda #1
    sta $08
:
.endif
@page:
    phx
    jsr ppu_pointer
    ldy #0
    lda a:$0005
.ifdef EXPERIMENTAL_WORD_FILL
    ; The checked aligned page contains one repeated byte. Duplicate it into
    ; a word and use native 16-bit stores; the final Y low byte is still zero.
    sta $06
    sta $07
    clc
    xce
    rep #$30
    .a16
    .i16
    lda $06
    ldy #0
@word_bytes:
    .repeat 8
        sta [$00],y
        iny
        iny
    .endrepeat
    cpy #256
    bne @word_bytes
    sep #$30
    .a8
    .i8
    sec
    xce
.else
@bytes:
    sta [$00],y
    iny
    bne @bytes
.endif
.ifdef EXPERIMENTAL_FILL_DIRTY_BATCH
    lda $08
    bne @page_done
.endif
    ; Ordinary pages need one mark per 32-byte tile row. The fourth page
    ; contains attributes: keep eight-byte sampling for every quadrant row.
    lda a:$1C27
    and #3
    cmp #3
    beq @attribute_stride
    lda #32
    bra @set_stride
@attribute_stride:
    lda #8
@set_stride:
    sta $06
@dirty:
    tya
    sta a:$1C26
    jsr mark_ppu_dirty
    tya
    clc
    adc $06
    tay
    bne @dirty
@page_done:
    stz a:$1C26
    inc a:$1C27
    plx
    dex
    bne @page
.ifdef EXPERIMENTAL_FILL_DIRTY_BATCH
    lda $08
    beq @batch_done
    lda #1
    sta a:$1C85
    ldx $09
    ldy #32
@batch_dirty:
    jsr dirty_mirrored_row
    inx
    dey
    bne @batch_dirty
    ldx #0
@batch_done:
.endif
    pld
    plp
    php
    pha
    lda a:$1C0A
    ora a:$1C83
    bne @done
    load_interrupt_enable
    beq @done
    sta $4200
@done:
    pla
    plp
    lda $05
    ldy #0
    ldx #0
    rts

; C575 copies Y bytes from the 64-byte graphics-command ring at $0545.
bulk_ring_loop:
    jsr bulk_ring_bytes
    jmp $C583
bulk_ring_bytes:
    php
    phd
    stz $4200
    lda #$1B
    xba
    lda #0
    tcd
.ifdef EXPERIMENTAL_RING_POINTER_CACHE
    ; The command ring overwhelmingly uses PPU increment-one writes. Resolve
    ; the mirrored SNES shadow pointer once and advance it directly until a
    ; logical page boundary; only a boundary can change CIRAM/CHR mapping.
    ; Palette aliases and increment-32 commands retain the byte-at-a-time path.
    lda a:$1C20
    and #4
    bne @byte
    lda a:$1C27
    and #$3F
    cmp #$3F
    beq @byte
    jsr ppu_pointer
@linear_byte:
    ; Long addressing distinguishes this independently tested fast store from
    ; the legacy stride/palette store used by corruption controls.
    lda f:$000545,x
    cmp [$00]
    beq @linear_unchanged
    sta [$00]
    phx
    jsr mark_ppu_dirty
    plx
@linear_unchanged:
    inc a:$1C09
    inx
    txa
    and #$3F
    tax
    inc a:$1C26
    bne @linear_same_page
    inc a:$1C27
    dey
    beq @bytes_done
    lda a:$1C27
    and #$3F
    cmp #$3F
    beq @byte
    jsr ppu_pointer
    bra @linear_byte
@linear_same_page:
    inc $00
    dey
    bne @linear_byte
    bra @bytes_done
.endif
@byte:
    jsr ppu_pointer
    lda a:$0545,x
    cmp [$00]
    beq @unchanged
    sta [$00]
    phx
    jsr mark_ppu_dirty
    plx
@unchanged:
    jsr ppu_increment
    inc a:$1C09
    inx
    txa
    and #$3F
    tax
    dey
    bne @byte
@bytes_done:
    pld
    plp
    php
    pha
    lda a:$1C0A
    ora a:$1C83
    bne @done
    load_interrupt_enable
    beq @done
    sta $4200
@done:
    pla
    plp
    txa
    ldy #0
    rts

.ifdef EXPERIMENTAL_NATIVE_COMMAND_PRODUCER
; Original CF04 builds one six-byte graphics-ring command and calls CAFD after
; every byte solely to increment/wrap X. Inline that exact four-instruction
; helper while retaining the original comparisons, two stack bytes, output
; order, A/X/Y result and final NZ/C/V state.
.macro command_producer_advance
    inx
    txa
    and #$3F
    tax
.endmacro
native_command_producer:
    cmp #$00
    beq @push_first
    cmp #$0B
    bne :+
    lda #$9F
    bra @push_first
:
    cmp #$3A
    bne :+
    lda #$00
    pha
    lda #$BA
    bra @push_second
:
    cmp #$70
    bcs :+
    lda #$00
    pha
    lda #$BA
    bra @push_second
:
    cmp #$B0
    bcs @push_first
    clc
    adc #$50
    pha
    lda #$AE
    bra @push_second
@push_first:
    pha
    lda #$00
@push_second:
    pha
    ldx a:$06B7
    lda $2B
    sta a:$0545,x
    command_producer_advance
    lda $2A
    sta a:$0545,x
    command_producer_advance
    lda #$04
    sta a:$0545,x
    command_producer_advance
    lda #$02
    sta a:$0545,x
    command_producer_advance
    pla
    sta a:$0545,x
    command_producer_advance
    pla
    sta a:$0545,x
    command_producer_advance
    stx a:$06B7
    rts
.endif

.ifdef EXPERIMENTAL_NATIVE_RING_CONSUMER
; C51B drains at most four queued graphics commands (one when $003E bit 1 is
; set). The translated loop repeatedly crosses the full PPU adapter for every
; address and data byte, making the intro queue drain slower than the NES.
; This replacement retains the original ring, budget and read-command ABI.
native_ring_consumer:
    lda a:$0004
    pha
    ldy #1
    lda a:$003E
    and #2
    bne @save_budget
    ldy #4
.ifdef EXPERIMENTAL_NATIVE_RING_BUDGET5
    lda a:$1CA0
    beq @save_budget
    iny
.endif
@save_budget:
    sty a:$0004
@command:
    lda a:$06B6
    tax
    cmp a:$06B7
    beq @finish
    ; LDA $2002 resets the shared NES PPU address latch.
    lda $4212
    stz a:$1C25
    lda a:$0545,x
    and #$3F
    sta a:$1C27
    jsr @advance
    lda a:$0545,x
    sta a:$1C26
    stz a:$1C25
    jsr @advance
    lda a:$0545,x
    bmi @read_command
    lda a:$00F8
    and #$FB
    ora a:$0545,x
    sta a:$00F8
.ifdef EXPERIMENTAL_CHR_DIRTY_GATE
    pha
    eor a:$1C20
    and #$18
    beq :+
    lda #1
    sta a:$1CBB
:
    pla
.endif
    sta a:$1C20
    jsr @advance
    lda a:$0545,x
    tay
    jsr @advance
    jsr bulk_ring_bytes
    stx a:$06B6
    dec a:$0004
    bne @command
    bra @finish
@read_command:
    ; Negative marker: consume a zero-page destination and perform two
    ; buffered reads. The reader uses adapter DP $1B00, as dispatch_read does.
    jsr @advance
    lda a:$0545,x
    tay
    jsr @advance
    php
    phx
    phy
    phd
    lda #$1B
    xba
    lda #0
    tcd
    jsr ppu_read_buffer
    jsr ppu_read_buffer
    pld
    ply
    plx
    plp
    lda a:$1B24
    sta a:$0000,y
    stx a:$06B6
    jmp @command
@finish:
    pla
    sta a:$0004
    ; The original tail writes zero twice to $2006 and returns A=0.
    stz a:$1C26
    stz a:$1C27
    stz a:$1C25
    php
    ; Match the translated PPU adapter's return policy: a caller already in
    ; NMI or a bank-pair critical section owns the interrupt-enable state.
    lda a:$1C0A
    ora a:$1C83
    bne @return_masked
    load_interrupt_enable
    sta $4200
@return_masked:
    plp
    lda #0
    rts
@advance:
    inx
    txa
    and #$3F
    tax
    rts
.endif

bank_switch_enter:
    ; Direct translation of FED1's paired-bank operation. The original routine
    ; uses four generic mapper writes, but their effect is fully determined by
    ; input A. Preserve its FB/FC/FD, R6/R7, A/X/Y and final CMP result.
    stz $4200
.ifdef EXPERIMENTAL_CHR_READ_CACHE
    stz a:$1B50
.endif
    inc a:$1C83
    pha
    asl
    sta $FC
    sta a:$1C16
    clc
    adc #1
    sta $FD
    sta a:$1C17
    lda #7
    sta $FB
    sta a:$1C19
    ; Match the adapter's existing 16-KiB-pair mapping, then jump into the
    ; replicated exit in the new bank. No extra return frame survives.
    pla
    pha
    and #7
    clc
    adc #$C1
    sta a:$1C03
    sta a:$1C02
    sta a:$1C8A
    ; C1..C8 program-bank mirrors map exactly to 81..88 data banks.
    eor #$40
    pha
    plb
    lda #<bank_switch_exit
    sta a:$1C88
    lda #>bank_switch_exit
    sta a:$1C89
    pla
    jml [$1C88]
bank_switch_exit:
    cmp $BFFF
    beq @valid
    ; Do not execute the NES undocumented $80 NOP as a 65816 BRA.
    inc a:$1C06
@invalid:
    bra @invalid
@valid:
    php
    pha
    dec a:$1C83
    lda a:$1C0A
    ora a:$1C83
    bne @return
    ; The pair is complete. Allow a pending VBlank NMI instead of discarding
    ; it by waiting for visible scanout. NMI entry acknowledges $4210, so an
    ; already-serviced edge cannot retrigger here. Late graphics are deferred.
    load_interrupt_enable
    sta $4200
@return:
    pla
    plp
    rts

.ifdef EXPERIMENTAL_GAMEPLAY_PREPARE_DEFER
camera_prepare_exit:
    ; Finish the original E2AF camera calculation before touching any flags.
    ; This hook replaces SBC $3B / STA $F6 / RTS as one indivisible tail.
    sbc $3B
    sta $F6
    php
    pha
    lda a:$1CBC
    beq @done
    ; Active gameplay ticks prepare after the camera commit instead of inside
    ; the NMI return path. The bridge preserves all original registers; the
    ; saved P restores the SBC result expected by E2AF's caller.
    stz $4200
    stz a:$1CBC
    inc a:$1CBE
    jsl $C00000+video_prepare_bridge
    load_interrupt_enable
    beq @done
    sta $4200
@done:
    pla
    plp
    rts
.endif

.ifdef EXPERIMENTAL_CAMERA_DEADLINE
; The normal port finishes sound publication and graphics preparation before
; returning from the original NMI.  That releases gameplay too late to compute
; RCR's camera before HDMA consumes the street entry at scanline 32.  This
; isolated experiment returns first, commits the live table at the exact
; original camera store, then performs retained work at the game's own F2C9
; end-of-iteration wait rather than blocking the rest of camera-bearing logic.
;
; Private experiment telemetry (all little-endian counters):
;   $1CD0 pending job
;   $1CD1..2 scheduled jobs
;   $1CD3..4 served jobs
;   $1CD5..6 next-NMI fallbacks
;   $1CD7..8 camera-tail executions
;   $1CD9 deadline armed only after the post-transition row queue drains
;   $1CDA..B jobs served at the F2C9 poll
camera_deadline_exit:
    ; Reproduce the complete overwritten E2AF tail.  P/A are restored exactly
    ; as the original SBC/STA/RTS left them after the live-table transaction.
    sbc $3B
    sta $F6
    php
    pha
    stz $4200
    lda $F6
    sta a:$1C94
    sta a:$1C97
    lda $3D
    and #1
    sta a:$1C95
    sta a:$1C98
    inc a:$1CD7
    bne :+
    inc a:$1CD8
:
@enable:
    load_interrupt_enable
    sta $4200
    pla
    plp
    rts

camera_deadline_poll:
    ; This hook replaces only F2C9's LDA $010B.  If a retained port job is
    ; ready, service it after the complete game iteration and then reproduce
    ; the original load for the untouched CMP/BCC wait.  Recheck after masking
    ; NMI so an interrupt in the small first-test window cannot duplicate work.
    ; Consume only genuine wait time.  If the game already has both NMI ticks,
    ; return immediately so port work cannot delay the next gameplay iteration;
    ; the counted next-NMI fallback will retain the packet/producer job.
    lda a:$010B
    cmp #2
    bcs @load_tick
    lda a:$1CD0
    beq @load_tick
    stz $4200
    lda a:$1CD0
    beq @enable
    stz a:$1CD0
    inc a:$1CD3
    bne :+
    inc a:$1CD4
:
    inc a:$1CDA
    bne :+
    inc a:$1CDB
:
    jsr gameplay_deadline_service
@enable:
    load_interrupt_enable
    sta $4200
@load_tick:
    lda a:$010B
    rts

gameplay_deadline_service:
    ; Keep RCR's own FA54/FF29 sound update in its original interrupt context.
    ; Only the port-added SPC packet publication and graphics producer move to
    ; the retained job.  Both bridges preserve their caller's registers.
    jsl $C00000+audio_publish_bridge
    jsl $C00000+video_prepare_bridge
    rts

camera_deadline_rows_drained:
    ; This is an arming-time proof, not a permanent dirty-row gate.  Once all
    ; 128 producer/consumer states are zero, ordinary gameplay changes may
    ; make them dirty without disabling the already-armed camera scheduler.
    ldx #0
@row:
    lda a:$1D00,x
    bne @dirty
    inx
    cpx #128
    bne @row
    sec
    rts
@dirty:
    clc
    rts
.endif

.ifdef EXPERIMENTAL_TRANSITION_WAIT_PREPARE
; Move only state-2 forced-blank row conversion into time that RCR would
; otherwise spend waiting for its second game tick at F2C9.  The NMI-side
; fallback below guarantees a retained pass cannot be overwritten.
;   $1CF0 pending pass
;   $1CF1..2 scheduled, $1CF3..4 served in wait, $1CF5..6 fallback
;   $1CF7 one-row budget override for the split pass
transition_wait_prepare_poll:
    php
    pha
    lda a:$010B
    cmp #2
    bcs @done
    lda a:$1CF0
    beq @done
    stz $4200
    lda a:$1CF0
    beq @enable
    stz a:$1CF0
    inc a:$1CF3
    bne :+
    inc a:$1CF4
:
    lda #1
    sta a:$1CF7
    jsl $C00000+video_prepare_bridge
    stz a:$1CF7
@enable:
    load_interrupt_enable
    sta $4200
@done:
    pla
    plp
    rts
.endif

.ifdef EXPERIMENTAL_DEFERRED_GAME_NMI
; Private experiment telemetry:
;   $1CE0 retained original-game NMI pending
;   $1CE1 main iteration is between F27D and E2A2
;   $1CE2..3 scheduled, $1CE4..5 served, $1CE6..7 fallback
;   $1CE8..A banked RTI trampoline, $1CEB post-transition armed
gameplay_iteration_start:
    lda #1
    sta a:$1CE1
    lda #0
    sta a:$010B
    jmp $F282

deferred_game_nmi_pause_gateway:
    ; Retarget only F289's taken $3F/$20 pause branch through the otherwise
    ; later F2E7 exit gateway.  Mark the camera-bearing portion complete before
    ; checking the retained latch: an NMI on either side of this store is then
    ; handled exactly once, and an NMI after it is never incorrectly deferred.
    ; The unpaused F28B..F2B4 update path remains completely untouched.
    stz a:$1CE1
    lda a:$1CE0
    beq deferred_game_nmi_pause_route
    stz a:$1CE0
    inc a:$1CE4
    bne :+
    inc a:$1CE5
:
    inc a:$1CE6
    bne :+
    inc a:$1CE7
:
    lda #>deferred_game_nmi_pause_return
    pha
    lda #<deferred_game_nmi_pause_return
    pha
    php
    inc a:$1C0A
    jml [$1C00]
deferred_game_nmi_pause_return:
deferred_game_nmi_pause_route:
    ; F2E7 is also the original destination when $38/$20 requests the outer
    ; game-loop exit.  Preserve that rare path; a genuine pause branch has the
    ; bit clear and rejoins the skipped-update path at F2B4.
    lda $38
    and #$20
    bne deferred_game_nmi_pause_exit
    jmp $F2B4
deferred_game_nmi_pause_exit:
    jsr $FC50
    jmp $F2EA

camera_deferred_nmi_exit:
    ; Complete the overwritten camera tail and publish its exact result before
    ; any retained game-NMI work.  P/A are restored to the original caller.
    sbc $3B
    sta $F6
    php
    pha
    ; Stay byte-for-byte close to the proven scheduler while a room is static.
    ; The first genuine camera/table difference arms future deferrals; this
    ; frame still publishes directly, so audited motion is corrected from the
    ; following game iteration without taxing transition drain loops.
    lda a:$1CEB
    bne @publish
    lda a:$1CA0
    bne camera_deferred_nmi_quick_return
    lda $F6
    cmp a:$1C94
.ifdef EXPERIMENTAL_STATIC_CAMERA_ARM
    bne @arm
    ; Stationary-camera actor processing can cross VBlank too. Only add
    ; early arming after the original fade completed; motion keeps its old
    ; arming rule. No pending job is created until a real NMI arrives.
    jsr camera_static_ready
    bcc camera_deferred_nmi_quick_return
@arm:
.else
    beq camera_deferred_nmi_quick_return
.endif
    lda #1
    sta a:$1CEB
@publish:
    stz $4200
.ifdef EXPERIMENTAL_CAMERA_SAFE_PUBLISH
    jsr camera_publish_safe
.else
    lda $F6
    sta a:$1C94
    sta a:$1C97
    lda $3D
    and #1
    sta a:$1C95
    sta a:$1C98
.endif
    stz a:$1CE1
.ifdef EXPERIMENTAL_SECOND_TICK_PREPARE
.ifdef EXPERIMENTAL_SECOND_TICK_DEADLINE
    jsr second_tick_prepare_camera
.else
    jsr second_tick_prepare_service
.endif
.endif
    lda a:$1CE0
    beq camera_deferred_nmi_enable
    stz a:$1CE0
    inc a:$1CE4
    bne :+
    inc a:$1CE5
:
    ; RTI pulls P, PCL, PCH.  Push the replicated-bank continuation high/low
    ; followed by a disposable status byte, exactly as an emulation interrupt.
    lda #>camera_deferred_nmi_return
    pha
    lda #<camera_deferred_nmi_return
    pha
    php
    inc a:$1C0A
    jml [$1C00]
camera_deferred_nmi_return:
    ; nmi_rti_return has already restored the normal interrupt-enable policy.
    pla
    plp
    rts
camera_deferred_nmi_enable:
.ifdef EXPERIMENTAL_CAMERA_NMI_REENABLE
    ; Camera data and iteration state are now committed, with no retained
    ; interrupt. A fresh VBlank edge while masked still deserves service.
    ; NMI entry acknowledges $4210; do not discard a new edge by waiting for
    ; active scanout, and do not clear $4210 here before enabling it.
    load_interrupt_enable
    sta $4200
.else
    ; An unretained camera can also land in late VBlank after the scheduler's
    ; phase shift.  Enabling NMI while $4210 is still asserted would fire a
    ; second, late interrupt whose publisher cannot finish before line 0.
@enable_outside_vblank:
    lda $4212
    bmi @enable_outside_vblank
    load_interrupt_enable
    sta $4200
.endif
camera_deferred_nmi_quick_return:
    pla
    plp
    rts
.ifdef EXPERIMENTAL_CAMERA_SAFE_PUBLISH
.include "camera_publish_safe.inc"
.endif
.ifdef EXPERIMENTAL_STATIC_CAMERA_ARM
.include "camera_static_ready.inc"
.endif
.endif

nmi_task_return:
    ; RCR's coroutine NMI deliberately consumes its interrupt frame and the
    ; FC60 wait routine's saved task/A, then RTSes to the caller of FC60.
    lda $F8
    and #$7F
    sta $F8
    sta a:$1C20
    stz $4200
.ifdef EXPERIMENTAL_SECOND_TICK_PREPARE
    jsr second_tick_prepare_fallback
.endif
    stz a:$1C25
.ifndef EXPERIMENTAL_FC60_DEFER_AUDIO
    jsl $C00000+audio_publish_bridge
.endif
.ifndef EXPERIMENTAL_FC60_DEFER_VIDEO
.ifdef EXPERIMENTAL_TRANSITION_PREPARE_DEFER
    lda a:$1CA0
    cmp #1
    bne :+
    lda a:$0042
    beq :++
:
.endif
    jsl $C00000+video_prepare_bridge
.ifdef EXPERIMENTAL_TRANSITION_PREPARE_DEFER
:
.endif
.endif
.ifdef EXPERIMENTAL_TRANSITION_GAME_FIRST
    lda a:$1CA0
    beq :+
    jsl $C00000+video_publish_bridge
:
.endif
    dec a:$1C0A
    pla
    pla
    pla
    pla
    sta $0100
    pla
    rts

.ifdef EXPERIMENTAL_FC60_DEFER
; Complete the native end-of-slice work immediately before the original game
; yields at FC60, rather than before its coroutine continuation can run.  The
; preceding NMI return deliberately leaves NMITIMEN clear, so both bridges run
; with the same non-reentrant guarantee as the old location.  Resume at FC64
; after reproducing the four overwritten bytes (PHA / LDA $0100).
fc60_deferred_work:
.ifdef EXPERIMENTAL_FC60_DEFER_AUDIO
    jsl $C00000+audio_publish_bridge
.endif
.ifdef EXPERIMENTAL_FC60_DEFER_VIDEO
    jsl $C00000+video_prepare_bridge
.endif
    pha
    lda $0100
    jmp $FC64
.endif

nmi_rti_return:
    stz $4200
.ifdef EXPERIMENTAL_SECOND_TICK_PREPARE
    jsr second_tick_prepare_fallback
.endif
.ifdef EXPERIMENTAL_CAMERA_DEADLINE
    ; A tick that never reached the camera path must be serviced before a new
    ; job can be scheduled.  Separate counters make overwrites and starvation
    ; observable instead of treating them as an emulator timing assumption.
    lda a:$1CD0
    beq @deadline_fallback_done
    stz a:$1CD0
    inc a:$1CD3
    bne @deadline_count_fallback
    inc a:$1CD4
@deadline_count_fallback:
    inc a:$1CD5
    bne :+
    inc a:$1CD6
:
    jsr gameplay_deadline_service
@deadline_fallback_done:
.endif
.ifdef EXPERIMENTAL_GAMEPLAY_PREPARE_DEFER
    stz a:$1CBA
    ; A gameplay tick normally clears this latch at the E2AA camera commit.
    ; If a scene did not execute that path, service the retained work at the
    ; next NMI rather than silently overwriting or starving it.
    lda a:$1CBC
    beq :+
    stz a:$1CBC
    inc a:$1CBF
    jsl $C00000+video_prepare_bridge
    lda #1
    sta a:$1CBA
:
.endif
    ; Gameplay ($0100 bits 7:6 == 11) ticks sound from the first MMC3 IRQ,
    ; unlike menu NMIs. Until raster IRQ translation exists, service that
    ; driver once here. This does NOT reproduce the original scanline timing.
    ; Match the IRQ's bank-variable save/restore around FA54. Original A/X/Y
    ; remain on the interrupt stack and are restored below.
.ifdef EXPERIMENTAL_EARLY_DEFERRED_AUDIO
    ; A fallback may be servicing a newer hardware NMI. Only the exact
    ; already-published 16-bit event ID suppresses this exit's driver/packet.
.ifdef EXPERIMENTAL_LATE_PREPARE_GUARD
    consume_early_audio @early_video
.else
    consume_early_audio @video_only
.endif
.endif
    lda a:$0100
    and #$C0
    cmp #$C0
    bne @prepared
    lda a:$0107
    bmi @prepared
.ifdef EXPERIMENTAL_RASTER
    jsr raster_arm
    bra @restore
.endif
    lda $FB
    pha
    lda $FC
    pha
    lda $FD
    pha
    jsr $FA54
    pla
    sta $FD
    pla
    sta $FC
    pla
    sta $FB
    jsr $FF29
    inc a:$1C84             ; $1C7C/D belongs to the VBlank beam diagnostic
.ifdef EXPERIMENTAL_CAMERA_DEADLINE
    ; Transition state 1/2 depends on immediate producer passes to expose a
    ; complete screen.  Preserve the established path until layers are live;
    ; the scanline-32 deadline exists only for visible gameplay.
    lda a:$1CA0
    beq @deadline_visible
    stz a:$1CD9
    bra @prepared
@deadline_visible:
    lda a:$1CD9
    bne @deadline_schedule
    jsr camera_deadline_rows_drained
    bcc @prepared
    lda #1
    sta a:$1CD9
@deadline_schedule:
    lda #1
    sta a:$1CD0
    inc a:$1CD1
    bne :+
    inc a:$1CD2
:
    bra @restore
.else
.ifdef EXPERIMENTAL_GAMEPLAY_PREPARE_DEFER
    lda #1
    sta a:$1CBC
    inc a:$1CBD
.endif
.endif
@prepared:
    jsl $C00000+audio_publish_bridge
.ifdef EXPERIMENTAL_LATE_PREPARE_GUARD
    bra @video_only
@early_video:
    jsr late_prepare_allowed
    bcs @video_only
    ; No row, sprite, palette or CHR ownership is consumed. The next normal
    ; NMI exit prepares the still-dirty source through the established path.
    jmp @restore
.endif
.ifdef EXPERIMENTAL_EARLY_DEFERRED_AUDIO
@video_only:
.endif
    ; Prepare the next frame after original game updates, not in the bounded
    ; SNES VBlank consumer. The bridge preserves the saved NES interrupt frame.
.ifdef EXPERIMENTAL_GAMEPLAY_PREPARE_DEFER
    lda a:$1CBC
    bne @restore
    lda a:$1CBA
    bne @restore
    ; Gameplay shadow state changes on the serviced game tick above.  Its
    ; camera hook (or the next-NMI fallback) performs one four-row producer
    ; pass; do not spend a second pass on the intervening display-only NMI.
    lda a:$0100
    and #$C0
    cmp #$C0
    beq @restore
.endif
.ifdef EXPERIMENTAL_SECOND_TICK_PREPARE
    jsr second_tick_prepare
.else
    jsl $C00000+video_prepare_bridge
.endif
@restore:
.ifdef EXPERIMENTAL_TRANSITION_GAME_FIRST
    lda a:$1CA0
    beq :+
    jsl $C00000+video_publish_bridge
:
.endif
.include "nmi_return_tail.inc"
apu_length_write:
    APU_LENGTH_WRITE
    rts
.ifdef EXPERIMENTAL_RASTER
; Isolated experiment: defer gameplay audio/preparation to a real timer IRQ.
; $1CA2 enable, $1CA3 pending, $1CA4..6 banked entry pointer.
; 16-bit counters: A8 scheduled, AA overwritten, AC served, AE late arm.
raster_arm:
.ifndef RASTER_LINE
RASTER_LINE = 30
.endif
    lda a:$1CA3
    beq :+
    inc a:$1CAA
    bne :+
    inc a:$1CAB
:
    lda #1
    sta a:$1CA3
    inc a:$1CA8
    bne :+
    inc a:$1CA9
:
    lda #<raster_worker
    sta a:$1CA4
    lda #>raster_worker
    sta a:$1CA5
    lda $4211
    lda #RASTER_LINE
    sta $4209
    sta a:$1CB2
    stz a:$1CB3
    stz $420A
    lda a:$1C04
    sta a:$1CB4
    lda a:$1C05
    sta a:$1CB5
    lda #$20
    sta a:$1CA2
    jsl $C10000+raster_rearm
    lda a:$1CB2
    cmp #RASTER_LINE
    beq :+
    inc a:$1CAE
    bne :+
    inc a:$1CAF
:
    rts
raster_rearm:
    ; E=1/A8. Hardware interrupt generation is masked at guarded callers.
    ; Preserve hidden accumulator B as well as caller A/X/Y/P.
    php
    cld
    pha
    lda a:$1CA3
    beq @quick
    lda a:$1C0A
    ora a:$1C83
    bne @quick
    phx
    phy
    clc
    xce
    rep #$30
    .a16
    .i16
    pha
    lda a:$1C04
    cmp a:$1CB4
    bne @finish
    sep #$20
    .a8
    lda $213F
    lda $2137
    lda $213D
    sta a:$1CB0
    lda $213D
    and #1
    sta a:$1CB1
    rep #$20
    .a16
    lda a:$1CB0
    ; Do not guess across VBlank/frame wrap. Unrecovered work stays visible
    ; to the missed-job counter. Timer target is the full nine-bit value.
    cmp #240
    bcs @finish
    inc
    cmp a:$1CB2
    bcc @finish
    clc
    adc #3
    sta a:$1CB2
    sep #$20
    .a8
    sta $4209
    lda a:$1CB3
    sta $420A
    rep #$20
    .a16
    inc a:$1CB8
@finish:
    pla
    sep #$30
    .a8
    .i8
    sec
    xce
    ply
    plx
@quick:
    pla
    plp
    rtl
raster_worker:
    pha
    phx
    phy
    stz $4200
    lda $4211
    stz a:$1CA2
    inc a:$1C0A
    lda a:$1CA3
    beq @done
    stz a:$1CA3
    lda $FB
    pha
    lda $FC
    pha
    lda $FD
    pha
    jsr $FA54
    pla
    sta $FD
    pla
    sta $FC
    pla
    sta $FB
    jsr $FF29
    inc a:$1C84
    jsl $C00000+audio_publish_bridge
    jsl $C00000+video_prepare_bridge
    inc a:$1CAC
    bne @done
    inc a:$1CAD
@done:
    dec a:$1C0A
    load_interrupt_enable
    sta $4200
    ply
    plx
    pla
    rti
.endif
.ifdef EXPERIMENTAL_CONTROL_PRESETS
; B=1, Y=2, A=4, X=8 in the four-bit physical key. Output is NES A/B.
; The dedicated jump button resolves to both NES attacks, as on the NES.
control_input_table:
    .byte 0,1,2,3,3,3,3,3, 0,1,2,3,3,3,3,3 ; Classic: B/Y/A
    .byte 0,2,0,2,1,3,1,3, 3,3,3,3,3,3,3,3 ; Nintendo: A/B/X
    .byte 0,3,1,3,0,3,1,3, 2,3,3,3,2,3,3,3 ; Arcade: Y/X/B
    .byte 0,2,1,3,3,3,3,3, 0,2,1,3,3,3,3,3 ; Reverse: Y/B/A
.endif
.ifdef EXPERIMENTAL_SPRITE_COORDINATES
; Append after existing code/data: enabling this helper must not relocate
; unrelated runtime branches or change their page-crossing timing.
    .a8
    .i8
    .include "sprite_coordinates.inc"
.endif
.ifdef EXPERIMENTAL_SECOND_TICK_PREPARE
    .a8
    .i8
    .include "second_tick_prepare.inc"
.endif
.ifdef EXPERIMENTAL_SPRITE_POSITION
    .a8
    .i8
    .include "sprite_position.inc"
.endif
.ifdef EXPERIMENTAL_JOYPAD_POLL
    .a8
    .i8
    .include "joypad_poll.inc"
.endif
.ifdef EXPERIMENTAL_SECOND_TICK_DEADLINE
    .a8
    .i8
    .include "second_tick_deadline.inc"
.endif
.ifdef EXPERIMENTAL_COLUMN_FETCH
    .a8
    .i8
    .include "column_fetch.inc"
.endif
.ifdef MAIN_PHASE_LINE
    .a8
    .i8
    .include "main_phase.inc"
.endif
