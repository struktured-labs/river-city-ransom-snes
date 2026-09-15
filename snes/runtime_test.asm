; Asset-free tests of the ACTUAL bank-replicated native adapter.
; Program copies in C0..C8 exercise real cross-bank returns.
.setcpu "65816"
.macpack longbranch
.a8
.i16
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
    lda #$80
    sta $2100
    stz $4200
    stz $420B
    stz $420C
    ldx #0
@clear:
    lda #0
    sta f:$7E0000,x
    sta f:$7F0000,x
    inx
    bne @clear
    lda #$C1
    sta $1C03
    lda #$81
    pha
    plb
    sep #$30
    .i8
    sec
    xce
    jml $C10000+tests
tests:
    ; Re-dirtying a staged row retains its ready bit; DMA must not starve.
    lda #2
    sta $1D00
    ; Ordinary buffered PPUDATA write/read, post-increment and register ABI.
    lda #1
    sta $1C61
    lda #$20
    ldx #6
    jsr ppu_write_test
    lda #$10
    jsr ppu_write_test
    lda #$AB
    ldx #7
    ldy #$56
    jsr ppu_write_test
    cmp #$AB
    jne failed
    cpx #7
    jne failed
    cpy #$56
    jne failed
    lda f:$7F2010
    cmp #$AB
    jne failed
    lda $1D00
    cmp #3
    jne failed
    lda $1C85
    cmp #1
    jne failed
    lda $1C26
    cmp #$11
    jne failed
    lda #$20
    ldx #6
    jsr ppu_write_test
    lda #$10
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test
    lda $1B24
    jne failed
    jsr ppu_read_test
    lda $1B24
    cmp #$AB
    jne failed
    ; MMC3 CHR slot 0 reads an original CHR byte, not converted display data.
    inc $1C61
    lda #$42
    sta $1C10
    lda #0
    ldx #6
    jsr ppu_write_test
    lda #$15
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test
    jsr ppu_read_test
    lda $1B24
    cmp #$D3
    beq :+
    jmp failed
:
    ; Read a unique sentinel from every raw CHR bank, crossing CF -> D0.
    lda #13
    sta $1C61
    stz $1C8F
    stz $1C19
    stz $1C20
@chr_banks:
    lda $1C8F
    sta $1C12             ; R2 is the 1-KiB slot at PPU $1000
    lda #$10
    ldx #6
    jsr ppu_write_test
    lda #$15
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test     ; discard previous buffer
    jsr ppu_read_test
    lda $1C8F
    eor #$91
    cmp $1B24
    jne failed
    inc $1C8F
    bpl @chr_banks
    jmp bulk_writer_tests_done
bulk_writer_tests:
    ; Whole decompression writer: page carry, ABI, and both PPUADDR phases.
    lda #14
    sta $1C61
    stz $1C25
    jsr bulk_test_input
    jsr bulk_ppu_byte
    jsr bulk_test_result
    lda f:$7F20FF
    cmp #$B6
    jne failed
    lda $1C26
    jne failed
    lda $1C27
    cmp #$21
    jne failed
    lda $1C25
    jne failed
    lda #1
    sta $1C25
    lda #4
    sta $1C20            ; swapped phase plus PPU increment 32
    jsr bulk_test_input
    jsr bulk_ppu_byte
    jsr bulk_test_result
    lda f:$7F3F20
    cmp #$B6
    jne failed
    lda $1C26
    cmp #$40
    jne failed
    lda $1C27
    cmp #$3F
    jne failed
    lda $1C25
    cmp #1
    jne failed
    stz $1C25
    stz $1C20
    lda #$FF
    sta $2C
    sta $2D
    jsr bulk_ppu_byte
    php
    cmp #0
    jne failed
    pla
    and #$83
    cmp #3               ; source $FFFF wraps to zero, Z and C set
    jne failed
    lda $2C
    ora $2D
    jne failed
    lda f:$7F3FFF
    cmp #$B6
    jne failed
    rts
bulk_writer_tests_done:
    ; Nonzero D must be preserved across long calls.
    lda #3
    sta $1C61
    lda #$12
    xba
    lda #$34
    tcd
    ldx #2
    jsr ppu_read_test
    tdc
    cmp #$34
    beq :+
    jmp failed
:
    xba
    cmp #$12
    beq :+
    jmp failed
:
    lda #0
    xba
    lda #0
    tcd
    ; Illegal dispatch is observable instead of being called a success.
    lda #4
    sta $1C61
    lda #$50
    sta $1B21
    jsl $C10000+dispatch_read
    lda $1C06
    cmp #1
    beq :+
    jmp failed
:
    stz $1C06
.ifdef CONTROLLER_TEST
    ; Test the real serial adapter: P1 Select only, P2 Start only.
    ; Opposite-port/cross-button leakage must fail too.
    lda #5
    sta $1C61
@input_visible:
    lda $4212
    bmi @input_visible
@input_blank:
    lda $4212
    bpl @input_blank
    lda #$40
    sta $1B21
    lda #$16
    sta $1B20
    lda #1
    sta $1B22
    jsl $C10000+dispatch_write
    stz $1B22
    jsl $C10000+dispatch_write
.ifdef JUMP_TEST
    lda #3
    sta $1C66
    lda #3
.else
    lda #4
    sta $1C66
    lda #8
.endif
    sta $1C67
    ldy #8
@read_buttons:
    lda #$16
    sta $1B20
    jsl $C10000+dispatch_read
    lda $1C66
    and #1
    cmp $1B24
    jne failed
    lsr $1C66
    lda #$17
    sta $1B20
    jsl $C10000+dispatch_read
    lda $1C67
    and #1
    cmp $1B24
    jne failed
    lsr $1C67
    dey
    bne @read_buttons
.endif
    ; Real OAM DMA path: copy all 256 distinct bytes and preserve caller ABI.
    lda #6
    sta $1C61
    ldx #0
@dma_source:
    txa
    sta $0200,x
    inx
    bne @dma_source
    lda #$40
    sta $1B21
    lda #$14
    sta $1B20
    lda #2
    sta $1B22
    lda #$78
    ldx #$34
    ldy #$56
    jsl $C10000+dispatch_write
    cmp #$78
    jne failed
    cpx #$34
    jne failed
    cpy #$56
    jne failed
    ldx #0
@dma_check:
    txa
    cmp $1000,x
    jne failed
    inx
    bne @dma_check
    ; A completed R6/R7 pair must retarget both program and data banks.
    lda #8
    sta $1C61
    lda #$80
    sta $1B21
    lda #1
    sta $1B20
    lda #6
    sta $1C19
    lda #2
    sta $1B22
    jsl $C10000+dispatch_write
    lda #7
    sta $1C19
    lda #3
    sta $1B22
    lda #$78
    ldx #$34
    ldy #$56
    jsl $C10000+dispatch_write
    cmp #$78
    jne failed
    cpx #$34
    jne failed
    cpy #$56
    jne failed
    phk
    pla
    cmp #$C2
    jne failed
    phb
    pla
    cmp #$82
    jne failed
    ; An ordinary call into the C1 helper must return to its C2 caller,
    ; preserving DB and registers without a return-bank rewrite.
    lda #$20
    ldx #6
    jsr ppu_write_test
    cmp #$20
    jne failed
    phk
    pla
    cmp #$C2
    jne failed
    phb
    pla
    cmp #$82
    jne failed
    lda #9
    sta $1C61
    stz $1C8B
@bank_loop:
    lda $1C8B
    ldx #$34
    ldy #$56
    jsr bank_switch_enter
    jne failed              ; final bank-tag CMP must report equality
    jcc failed
    cmp $1C8B
    jne failed
    cpx #$34
    jne failed
    cpy #$56
    jne failed
    lda $1C8B
    clc
    adc #$C1
    sta $1C8C
    phk
    pla
    cmp $1C8C
    jne failed
    lda $1C8B
    clc
    adc #$81
    sta $1C8C
    phb
    pla
    cmp $1C8C
    jne failed
    lda $1C8B
    asl
    cmp $FC
    jne failed
    cmp $1C16
    jne failed
    clc
    adc #1
    cmp $FD
    jne failed
    cmp $1C17
    jne failed
    lda $FB
    cmp #7
    jne failed
    lda $1C83
    jne failed
    inc $1C8B
    lda $1C8B
    cmp #8
    jcc @bank_loop
    ; Execute the production-generated mailbox stub, not just its handler.
    ; Each independent guard must suppress real hardware NMIs across VBlank.
    lda #10
    sta $1C61
    lda #$80
    sta $1C20
    lda #1
    sta $1C0A
    jsr guarded_io_test
    stz $1C0A
    lda #1
    sta $1C83
    jsr guarded_io_test
    stz $1C83
    stz $1C20
    ; Verify the PPUMASK preparation scheduling contract independently from
    ; the pixel test: initial/NMI-disabled loads prepare synchronously, while
    ; active NMI work and established pipelines defer to the NMI exit.
    lda #11
    sta $1C61
    stz $1C79
    jsr mask_test_write
    lda $1C8E
    cmp #1
    jne failed
    lda #1
    sta $1C79
    jsr mask_test_write
    lda $1C8E
    cmp #2
    jne failed
    lda #$80
    sta $1C20
    jsr mask_test_write
    lda $1C8E
    cmp #2
    jne failed
    lda #1
    sta $1C0A
    stz $1C20
    jsr mask_test_write
    lda $1C8E
    cmp #2
    jne failed
    stz $1C0A
    stz $1C79
    lda #12
    sta $1C61
    lda #$FF
    sta $1B20
    sta $1B21
    lda #$20
    sta $1C27
    lda #$10
    sta $1C26
    lda #$A5
    sta f:$7F2010
    lda #$5A
    sta $1C2A
    ldx #$34
    ldy #$56
    sec
    jsr io_read_stub
    jcc failed
    cmp #$5A                ; first read returns the old buffer
    jne failed
    cpx #$34
    jne failed
    cpy #$56
    jne failed
    lda $1C2A
    cmp #$A5
    jne failed
    lda $1C26
    cmp #$11
    jne failed
    jsr io_read_stub
    jpl failed              ; LDA result must set N from the returned $A5
    cmp #$A5
    jne failed
    lda #$3F
    sta $1C27
    stz $1C26
    lda #$37
    sta f:$7F3F00
    lda #4                  ; 32-byte address increment
    sta $1C20
    jsr io_read_stub
    cmp #$37                ; palette reads bypass the old read buffer
    jne failed
    lda $1C26
    cmp #$20
    jne failed
    stz $1C20
    jsr bulk_writer_tests
    jsr bulk_reader_tests
    jsr page_fill_tests
    jsr ring_loop_tests
    jsr pulse_reload_tests
    lda #1
    sta $1C60
    stz $2121
    lda #$E0
    sta $2122
    lda #3
    sta $2122
    lda #$0F
    sta $2100
@visible:
    lda $4212
    bmi @visible
@blank:
    lda $4212
    bpl @blank
    inc $1C62
    bne @visible
    inc $1C63
    bra @visible
failed:
    lda #$EE
    sta $1C60
    bra failed
guarded_io_test:
    lda #$20
    sta $1C27
    lda #$10
    sta $1C26
    lda #2
    sta $1D00
    lda #$FF
    sta $1B20
    sta $1B21              ; specialized stub must not consult stale address
    lda #$A5
    ldx #$34
    ldy #$56
    sec
    jsr io_write_stub
    jcc failed
    cmp #$A5
    jne failed
    cpx #$34
    jne failed
    cpy #$56
    jne failed
    lda f:$7F2010
    cmp #$A5
    jne failed
    lda $1C26
    cmp #$11
    jne failed
    lda $1D00
    cmp #3
    jne failed
@visible:
    lda $4212
    bmi @visible
@blank:
    lda $4212
    bpl @blank
@after:
    lda $4212
    bmi @after
    stz $4200
    lda $1C8D
    jne failed
    rts
pulse_reload_tests:
    lda #18
    sta $1C61
    lda #$40
    sta $1B21
    stz $1B22           ; a zero timer write must not be missed
    stz $0A16
    lda #2
    sta $1B20
    jsl $C10000+dispatch_write
    lda $0A16
    cmp #$40
    jne failed
    inc $1B20
    jsl $C10000+dispatch_write
    lda $0A16
    cmp #$41
    jne failed
    lda #6
    sta $1B20
    jsl $C10000+dispatch_write
    lda $0A16
    cmp #$C1
    jne failed
    inc $1B20
    jsl $C10000+dispatch_write
    lda $0A16
    cmp #$C3
    jne failed
    stz $0A16
    lda #$15
    sta $1B20
    jsl $C10000+dispatch_write
    lda $0A16
    jne failed
    rts
ring_loop_tests:
    lda #17
    sta $1C61
    ldx #63
@source:
    txa
    eor #$A5
    sta $0545,x
    dex
    bpl @source
    ldx #127
    lda #2
@dirty_init:
    sta $1D00,x
    dex
    bpl @dirty_init
    stz $1C20
    lda #$20
    sta $1C27
    lda #$FE
    sta $1C26
    ldx #61
    ldy #5
    sec
    jsr bulk_ring_bytes
    php
    cmp #2
    jne failed
    pla
    and #$83
    cmp #3
    jne failed
    cpx #2
    jne failed
    cpy #0
    jne failed
    lda $1C26
    cmp #3
    jne failed
    lda $1C27
    cmp #$21
    jne failed
    lda f:$7F20FE
    cmp #$98
    jne failed
    lda f:$7F20FF
    cmp #$9B
    jne failed
    lda f:$7F2100
    cmp #$9A
    jne failed
    lda f:$7F2101
    cmp #$A5
    jne failed
    lda f:$7F2102
    cmp #$A4
    jne failed
    lda $1D07
    and $1D08
    cmp #3
    jne failed
    lda $1D06
    ora $1D09
    cmp #2
    jne failed
    ; Y=0 means 256 bytes; cover all four ring wraps with PPU stride 32.
    lda #4
    sta $1C20
    stz $1C26
    lda #$20
    sta $1C27
    ldx #63
    ldy #0
    jsr bulk_ring_bytes
    cmp #63
    jne failed
    cpx #63
    jne failed
    lda $1C26
    jne failed
    lda $1C27
    cmp #$40
    jne failed
    stz $07
    lda #$20
    sta $08
    lda #$7F
    sta $09
    stz $1C8F
@oracle:
    txa
    eor #$A5
    cmp [$07],y
    jne failed
    txa
    clc
    adc #1
    and #63
    tax
    lda $07
    clc
    adc #32
    sta $07
    bcc :+
    inc $08
:
    dec $1C8F
    bne @oracle
    stz $1C20
    rts
page_fill_tests:
    lda #16
    sta $1C61
    ldx #127
    lda #2
@flags:
    sta $1D00,x
    dex
    bpl @flags
    stz $1C85
    stz $1C26
    stz $1C20
    lda #$23            ; only last page: attributes must dirty ALL 32 rows
    sta $1C27
    lda #$A9
    sta $05
    ldx #1
    sec
    jsr bulk_fill_pages
    php
    cmp #$A9
    jne failed
    pla
    and #$83
    cmp #3              ; original C retained, X/Y zero -> Z set
    jne failed
    cpx #0
    jne failed
    cpy #0
    jne failed
    lda $1C27
    cmp #$24
    jne failed
    lda $1C26
    jne failed
    lda $1C85
    cmp #1
    jne failed
    ldx #0
@check_flags:
    lda #3
    cpx #32
    bcc :+
    lda #2
:
    cmp $1D00,x
    jne failed
    inx
    bpl @check_flags
    lda #$7F
    sta $09
    stz $07
    lda #$23
    sta $08
    ldy #0
@check_page:
    lda [$07],y
    cmp #$A9
    jne failed
    iny
    bne @check_page
    inc $08
    lda $08
    cmp #$24
    bne @check_page
    ; X=0 means 256 pages, including repeated 14-bit shadow wrap.
    lda #$20
    sta $1C27
    lda #$5A
    sta $05
    ldx #0
    jsr bulk_fill_pages
    lda $1C27
    cmp #$20
    jne failed
    stz $08
@check_all:
    lda [$07],y
    cmp #$5A
    jne failed
    iny
    bne @check_all
    inc $08
    lda $08
    cmp #$40
    bne @check_all
    rts
bulk_reader_tests:
    lda #15
    sta $1C61
    lda #64
    sta $1C12
    lda #$16
    sta $2A
    lda #$0F
    sta $2B
    lda #$FF
    sta $1A
    ldx #$34
    ldy #$56
    jsr bulk_source_byte
    php
    cmp #$D1
    jne failed
    pla
    and #$83
    cmp #2              ; index FF -> 00 gives Z; source addition has no carry
    jne failed
    lda $1A
    jne failed
    lda $1B
    cmp #$D1
    jne failed
    cpx #$34
    jne failed
    cpy #$56
    jne failed
    lda $1C26
    cmp #$17
    jne failed
    lda $1C27
    cmp #$10
    jne failed
    lda $1C2A
    cmp #$FF            ; buffer contains the byte AFTER the returned sentinel
    jne failed
    lda #$A5
    sta f:$7F2100
    lda #$5A
    sta f:$7F2120
    lda #$FF
    sta $2A
    lda #$20
    sta $2B
    lda #1
    sta $1A
    lda #4
    sta $1C20
    jsr bulk_source_byte
    cmp #$A5
    jne failed
    lda $1C2A
    cmp #$5A
    jne failed
    lda $1C26
    cmp #$40
    jne failed
    lda $1C27
    cmp #$21
    jne failed
    stz $1C20
    lda #1
    sta $1C25
    sta $1A
    lda #$3E
    sta $2A
    lda #$E9
    sta f:$7F3F21
    jsr bulk_source_byte
    cmp #$E9            ; swapped address phase -> palette bypass at $3F21
    jne failed
    lda $1C26
    cmp #$22
    jne failed
    lda $1C27
    cmp #$3F
    jne failed
    lda $1C25
    cmp #1
    jne failed
    stz $1C25
    stz $2A
    stz $1A
    lda #$80
    sta $2B
    jsr bulk_source_byte
    jcc failed          ; original CMP selects CPU path with carry set
    cmp #$78            ; first byte of replicated fixture program: SEI
    jne failed
    cpy #0
    jne failed
    cpx #$34
    jne failed
    lda $1A
    cmp #1
    jne failed
    rts
bulk_test_input:
    lda #$B6
    sta $1B
    lda #$FF
    sta $2C
    lda #$20
    sta $2D
    ldx #$34
    ldy #$56
    rts
bulk_test_result:
    php
    cmp #$21
    jne failed
    pla
    and #$83
    jne failed           ; final high-byte ADC gives N=Z=C=0
    cpx #$34
    jne failed
    cpy #$56
    jne failed
    lda $2C
    jne failed
    lda $2D
    cmp #$21
    jne failed
    rts
mask_test_write:
    lda #$18
    ldx #1
    jsr ppu_write_test
    cmp #$18
    jne failed
    lda $1C21
    cmp #$18
    jne failed
    rts
ppu_write_test:
    sta $1B22
    stx $1B20
    pha
    lda #$20
    sta $1B21
    pla
    jsl $C10000+dispatch_write
    rts
ppu_read_test:
    stx $1B20
    lda #$20
    sta $1B21
    jsl $C10000+dispatch_read
    rts
interrupt:
    pha
    lda $4210
    inc $1C8D
    pla
    rti
.segment "HEADER"
    .byte "RCR ADAPTER TESTS    "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
