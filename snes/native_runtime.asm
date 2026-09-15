; Bank-replicated E=1 runtime. DB always mirrors the active HiROM bank ($81-$88).
; Hook ABI: $1B20/21 = effective address, $1B22 = write data, $1B24 = read result.
; Trace-covered game PPU/APU writes and MMC3 paired PRG switching.
; Bootstrap publishes graphics/audio; raster IRQ and full mapper fidelity remain open.
.setcpu "65816"
.a8
.i8
.segment "CODE"
dispatch_write:
    jsr trace_caller
    php
    pha
    phx
    phy
    phd
    lda a:$1C20
    and #$80
    sta a:$1B26
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
    beq console_write
    cmp #$80
    beq mapper_write
    cmp #$A0
    beq mirror_write
    cmp #$C0
    beq mapper_irq
    cmp #$E0
    beq mapper_irq
    inc a:$1C06
    jmp done
mirror_write:
    lda $22
    sta a:$1C18
    jmp done
mapper_irq:
    ; Store IRQ register activity for the later timing adapter; do not pretend
    ; this CPU proof implements scanline splits.
    inc a:$1C07
    jmp done
mapper_write:
    lda $20
    and #1
    bne @data
    lda $22
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
    jmp done
@chr:
    inc a:$1C08
    jmp done
console_write:
    lda $20
    cmp #$14
    beq @dma
    cmp #$16
    beq @joy
    cmp #$18
    bcs @end
    tax
    lda $22
    sta a:$0A00,x
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
    cpx #0
    bne @joy_done
    and #1
    beq @joy_done
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
@joy_done:
    jmp done
@dma:
    lda #0
    sta $00
    lda $22
    sta $01
    lda #$7E
    sta $02
    ldy #0
@copy:
    lda [$00],y
    sta a:$1000,y
    iny
    bne @copy
    jmp done
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
    beq @oamaddr
    cpx #4
    beq @oamdata
    cpx #5
    beq @scroll
    cpx #6
    beq @addr
    cpx #7
    beq @data
    jmp done
@ctrl:
    sta a:$1C20
    stz a:$1B26            ; unique tail hook enables NMI after its stack is gone
    jmp done
@mask:
    sta a:$1C21
    jsl $C00000+video_prepare_bridge
    jmp done
@oamaddr:
    sta a:$1C23
    jmp done
@oamdata:
    ldx a:$1C23
    sta a:$1000,x
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
    jsr ppu_pointer
    lda $22
    sta [$00]
    jsr mark_ppu_dirty
    jsr ppu_increment
    inc a:$1C09
    jmp done

mark_ppu_dirty:
    lda a:$1C27
    cmp #$20
    bcc @end
    cmp #$30
    bcs @end
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
    lda a:$1D00,x
    ora #1
    sta a:$1D00,x
    lda a:$1D01,x
    ora #1
    sta a:$1D01,x
    lda a:$1D02,x
    ora #1
    sta a:$1D02,x
    lda a:$1D03,x
    ora #1
    sta a:$1D03,x
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
    lda a:$1D00,x
    ora #1
    sta a:$1D00,x
@end:
    rts

dispatch_read:
    jsr trace_caller
    php
    pha
    phx
    phy
    phd
    lda a:$1C20
    and #$80
    sta a:$1B26
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
:
    jsr ppu_increment
    jmp done

ppu_pointer:
    lda a:$1C26
    sta $00
    lda a:$1C27
    and #$3F
    sta $01
    lda #$7F
    sta $02
    rts
chr_read_pointer:
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
    sta $04
    lsr
    lsr
    lsr
    lsr
    lsr
    lsr
    clc
    adc #$CF
    sta $02
    lda $04
    asl
    asl
    sta $01
    lda a:$1C27
    and #3
    ora $01
    sta $01
@done:
    rts
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

bank_switch_enter:
    ; Keep R6/R7 pair writes atomic against the NMI's audio-bank switch.
    ; Replay the three replaced original instructions with identical stack ABI.
    stz $4200
    inc a:$1C83
    pha
    txa
    pha
    jmp $FED4
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
@outside:
    lda $4212
    bmi @outside
    lda a:$1C20
    and #$80
    sta $4200
@return:
    pla
    plp
    rts

nmi_task_return:
    ; RCR's coroutine NMI deliberately consumes its interrupt frame and the
    ; FC60 wait routine's saved task/A, then RTSes to the caller of FC60.
    lda $F8
    and #$7F
    sta $F8
    sta a:$1C20
    stz $4200
    stz a:$1C25
    jsl $C00000+video_prepare_bridge
    dec a:$1C0A
    pla
    pla
    pla
    pla
    sta $0100
    pla
    rts

nmi_rti_return:
    stz $4200
    ; Gameplay ($0100 bits 7:6 == 11) ticks sound from the first MMC3 IRQ,
    ; unlike menu NMIs. Until raster IRQ translation exists, service that
    ; driver once here. This does NOT reproduce the original scanline timing.
    ; Match the IRQ's bank-variable save/restore around FA54. Original A/X/Y
    ; remain on the interrupt stack and are restored below.
    lda a:$0100
    and #$C0
    cmp #$C0
    bne @prepared
    lda a:$0107
    bmi @prepared
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
    inc a:$1C7C
@prepared:
    ; Prepare the next frame after original game updates, not in the bounded
    ; SNES VBlank consumer. The bridge preserves the saved NES interrupt frame.
    jsl $C00000+video_prepare_bridge
    pla
    tay
    pla
    tax
    pla
    pha
@outside_vblank:
    lda $4212
    bmi @outside_vblank
    dec a:$1C0A
    lda a:$1C20
    and #$80
    sta $4200
    pla
    rti
