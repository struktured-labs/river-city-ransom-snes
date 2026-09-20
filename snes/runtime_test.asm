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
.ifdef FASTROM_TEST
    lda #1
    sta $420D
.endif
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
.ifdef NAMETABLE_TEST
    jsr nametable_alias_tests
    jmp test_success
.endif
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
    ; Exercise actual mapper transactions, not direct mutation of its shadow.
    ; The latter bypasses production cache invalidation and is not hardware.
.ifndef CHR_TEST_HIGH
CHR_TEST_HIGH=$10
.endif
.ifndef CHR_TEST_MODE
CHR_TEST_MODE=0
.endif
CHR_TEST_SLOT=(CHR_TEST_HIGH >> 2) ^ (CHR_TEST_MODE >> 5)
.if CHR_TEST_SLOT < 4
CHR_TEST_REGISTER=CHR_TEST_SLOT >> 1
.else
CHR_TEST_REGISTER=CHR_TEST_SLOT-2
.endif
CHR_TEST_ALT_SLOT=CHR_TEST_SLOT ^ 4
.if CHR_TEST_ALT_SLOT < 4
CHR_TEST_ALT_REGISTER=CHR_TEST_ALT_SLOT >> 1
.else
CHR_TEST_ALT_REGISTER=CHR_TEST_ALT_SLOT-2
.endif
CHR_TEST_NORMAL_SLOT=CHR_TEST_HIGH >> 2
.if CHR_TEST_NORMAL_SLOT < 4
CHR_TEST_NORMAL_REGISTER=CHR_TEST_NORMAL_SLOT >> 1
.else
CHR_TEST_NORMAL_REGISTER=CHR_TEST_NORMAL_SLOT-2
.endif
    lda $1C10+CHR_TEST_REGISTER
    pha
@chr_banks:
    lda #$80
    sta $1B21
    stz $1B20
    lda #CHR_TEST_MODE | CHR_TEST_REGISTER
    sta $1B22
    jsl $C10000+dispatch_write
    lda #1
    sta $1B20
    lda $1C8F
    sta $1B22
    jsl $C10000+dispatch_write
    ; Repeat the identical address: the second buffered pair must return a
    ; cache-hit byte, not only the first miss's correctly resolved byte.
    .repeat 2
    lda #CHR_TEST_HIGH
    ldx #6
    jsr ppu_write_test
    lda #$15
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test     ; discard previous buffer
    jsr ppu_read_test
    lda $1C8F
.if CHR_TEST_SLOT < 4
    and #$FE
    ora #CHR_TEST_SLOT & 1
.endif
    and #$7F
    eor #(CHR_TEST_HIGH & 3)*$33
    eor #$91
    cmp $1B24
    jne failed
    .endrepeat
    ; Exercise the public decompressor reader in both PPU increment modes.
    ; The next byte and +32 lookahead are filler, not the bank sentinel.
    .repeat 2, stride
    lda #stride*4
    sta $1C20
    lda #$15
    sta $2A
    lda #CHR_TEST_HIGH
    sta $2B
    stz $1A
    lda #$A5
    sta $1C2A           ; stale buffer must be replaced by the lookahead
    ldx #$34
    ldy #$56
    jsr bulk_source_byte
    cpx #$34
    jne failed
    cpy #$56
    jne failed
    lda $1C8F
.if CHR_TEST_SLOT < 4
    and #$FE
    ora #CHR_TEST_SLOT & 1
.endif
    and #$7F
    eor #(CHR_TEST_HIGH & 3)*$33
    eor #$91
    cmp $1B
    jne failed
    cmp $1B24
    jne failed
    lda $1C2A
    cmp #$FF
    jne failed
    lda $1C26
    cmp #$17+stride*$3E
    jne failed
    lda $1C27
    cmp #CHR_TEST_HIGH
    jne failed
    lda $1A
    cmp #1
    jne failed
    .endrepeat
    stz $1C20
    ; Change the page without mapper writes: a stale page key must fail.
    lda #CHR_TEST_HIGH ^ 1
    ldx #6
    jsr ppu_write_test
    lda #$15
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test
    jsr ppu_read_test
    lda $1C8F
.if CHR_TEST_SLOT < 4
    and #$FE
    ora #CHR_TEST_SLOT & 1
.endif
    and #$7F
    eor #((CHR_TEST_HIGH ^ 1) & 3)*$33
    eor #$91
    cmp $1B24
    jne failed
    ; Invert slots with only a selector write, not a data write.
    stz $1B20
    lda #$80
    sta $1B21
    lda #(CHR_TEST_MODE ^ $80) | CHR_TEST_REGISTER
    sta $1B22
    jsl $C10000+dispatch_write
    lda #CHR_TEST_HIGH
    ldx #6
    jsr ppu_write_test
    lda #$15
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test
    jsr ppu_read_test
    lda $1C10+CHR_TEST_ALT_REGISTER
.if CHR_TEST_ALT_SLOT < 4
    and #$FE
    ora #CHR_TEST_ALT_SLOT & 1
.endif
    and #$7F
    eor #(CHR_TEST_HIGH & 3)*$33
    eor #$91
    cmp $1B24
    jne failed
.ifdef TEST_BANK_RESTORE
    ; These optimized mapper paths bypass dispatch_write. Qualify their
    ; invalidation too, with a live cached page and unchanged PPU address.
    lda #0
    jsr bank_switch_enter
    lda #CHR_TEST_HIGH
    ldx #6
    jsr ppu_write_test
    lda #$15
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test
    jsr ppu_read_test
    lda $1C10+CHR_TEST_NORMAL_REGISTER
.if CHR_TEST_NORMAL_SLOT < 4
    and #$FE
    ora #CHR_TEST_NORMAL_SLOT & 1
.endif
    and #$7F
    eor #(CHR_TEST_HIGH & 3)*$33
    eor #$91
    cmp $1B24
    jne failed
    stz $FC
    lda #1
    sta $FD
    lda #(CHR_TEST_MODE ^ $80) | 7
    sta $FB
    jsr native_bank_restore
    lda #CHR_TEST_HIGH
    ldx #6
    jsr ppu_write_test
    lda #$15
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test
    jsr ppu_read_test
    lda $1C10+CHR_TEST_ALT_REGISTER
.if CHR_TEST_ALT_SLOT < 4
    and #$FE
    ora #CHR_TEST_ALT_SLOT & 1
.endif
    and #$7F
    eor #(CHR_TEST_HIGH & 3)*$33
    eor #$91
    cmp $1B24
    jne failed
.endif
    inc $1C8F
    jne @chr_banks
    pla
    sta $1C10+CHR_TEST_REGISTER
    stz $1C19            ; restore fixture setup for unrelated adapter cases
    stz $1B50
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
    ; Repeating the identical byte preserves clean row state, but still
    ; performs the PPU/source increments, ABI result and write accounting.
    stz $1D07
    stz $1D47
    stz $1C85
    stz $1C09
    jsr bulk_test_input
    jsr bulk_ppu_byte
    jsr bulk_test_result
    lda $1D07
    ora $1D47
    ora $1C85
    jne failed
    lda $1C09
    cmp #1
    jne failed
    lda $1C26
    jne failed
    lda $1C27
    cmp #$21
    jne failed
    lda #1
    sta $1C25
    lda #4
    sta $1C20            ; swapped phase plus PPU increment 32
    jsr bulk_test_input
    jsr bulk_ppu_byte
    jsr bulk_test_result
    lda f:$7F3F00        ; $3F20 aliases the universal backdrop
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
    lda f:$7F3F1F        ; $3FFF wraps within the 32-byte palette
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
.ifdef OAM_DMA_PAGE
    sta f:$7E0000+OAM_DMA_PAGE*256,x
.else
    sta $0200,x
.endif
    inx
    bne @dma_source
    lda #$40
    sta $1B21
    lda #$14
    sta $1B20
.ifdef OAM_DMA_PAGE
    lda #OAM_DMA_PAGE
.else
    lda #2
.endif
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
.ifdef OAM_DMA_PAGE
    ; Stack-page bytes include the actual dispatcher pushes. Comparing the
    ; retained source after return accounts for those bytes without writing
    ; or manufacturing an expected stack snapshot.
    lda f:$7E0000+OAM_DMA_PAGE*256,x
.else
    txa
.endif
    cmp $1000,x
    jne failed
    inx
    bne @dma_check
.ifdef OAM_DMA_PAGE
    ; Verify DB and both bytes of D only after checking stack-page snapshot
    ; data, so these additional fixture pushes cannot change that expected data.
    phb
    pla
    cmp #$81
    jne failed
    phd
    pla
    cmp #0
    jne failed
    pla
    cmp #0
    jne failed
    jmp test_success
.endif
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
    lda #3
    sta $1D00
    lda #0
    ldx #1
    jsr ppu_write_test
    lda $1C8E                ; blanking must not run the producer
    jne failed
    lda $1D00                ; pending/stale state survives until render-on
    cmp #3
    jne failed
    lda $1CA0
    cmp #1
    jne failed
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
    jsr palette_alias_tests
    jsr palette_buffer_tests
    jsr bulk_writer_tests
    jsr bulk_reader_tests
    jsr page_fill_tests
    jsr ring_loop_tests
.ifdef EXPERIMENTAL_NATIVE_RING_CONSUMER
    jsr native_ring_consumer_tests
.endif
    jsr pulse_reload_tests
    jsr transition_snapshot_tests
    jsr unchanged_ppu_tests
    jsr length_eligibility_tests
    jsr rect_run_tests
    jsr repeat_run_tests
    jsr register_ppudata_tests
    jsr attribute_fill_tests
    jsr literal_copy_tests
test_success:
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
literal_copy_tests:
    lda #30
    sta $1C61
    stz $4200
    stz $1C20
    stz $1C25
    stz $1C18
    stz $1C19
    stz $1C10
    stz $1B50            ; fixture snapshot setup also resets derived CHR cache
    stz $1C09
    lda #$5A
    sta $1C2A
    stz $2A
    stz $2B
    lda #$14
    sta $1A
    lda #$BF
    sta $2C
    lda #$23
    sta $2D
    lda #0
    sta f:$7F23BF
    sta f:$7F23C0
    ldx #127
:
    stz $1D00,x
    dex
    bpl :-
    ldx #2
    ldy #$A6
    jsr bulk_literal_bytes
    php
    cmp #$23
    jne failed
    cpx #0
    jne failed
    cpy #$A6
    jne failed
    pla
    and #$C3
    cmp #2
    jne failed
    lda f:$7F23BF
    cmp #$FF
    jne failed
    lda f:$7F23C0
    cmp #$91
    jne failed
    lda $1B
    cmp #$91
    jne failed
    lda $1B24
    cmp #$91
    jne failed
    lda $1C2A
    cmp #$FF
    jne failed
    lda $1A
    cmp #$16
    jne failed
    lda $2E
    cmp #$15
    jne failed
    lda $2F
    jne failed
    lda $2C
    cmp #$C1
    jne failed
    cmp $1C26
    jne failed
    lda $1C27
    cmp #$23
    jne failed
    lda $1C09
    cmp #2
    jne failed
    ldx #127
@flags:
    txa
    and #$3F
    cmp #4
    bcc @dirty
    cmp #29
    beq @dirty
    lda #0
    bra @compare
@dirty:
    lda #1
@compare:
    cmp $1D00,x
    jne failed
    dex
    bpl @flags
    ; Destination page crossing must fall back and remap physical CIRAM.
    lda #$14
    sta $1A
    lda #$FF
    sta $2C
    lda #$23
    sta $2D
    lda #0
    sta f:$7F23FF
    sta f:$7F2400
    ldx #2
    jsr bulk_literal_bytes
    lda f:$7F23FF
    cmp #$FF
    jne failed
    lda f:$7F2400
    cmp #$91
    jne failed
    lda $2C
    cmp #1
    jne failed
    lda $2D
    cmp #$24
    jne failed
    ; Source index wraps independently of base-address addition.
    lda #$FF
    sta $1A
    lda #$16
    sta $2A
    ldx #2
    jsr bulk_literal_bytes
    lda $1A
    cmp #1
    jne failed
    lda $2E
    cmp #$16
    jne failed
    lda $2F
    jne failed
    ; Enabled NMI uses the original helpers, even away from boundaries.
    lda #1
    sta $1C0A
    lda #$80
    sta $1C20
    stz $2A
    stz $2C
    lda #$14
    sta $1A
    ldx #2
    jsr bulk_literal_bytes
    lda f:$7F2401
    cmp #$91
    jne failed
    lda $1A
    cmp #$16
    jne failed
    stz $1C20
    stz $1C0A
    rts
attribute_fill_tests:
    lda #29
    sta $1C61
    stz $4200
    stz $1C18
    stz $1C25
    .repeat 2, enabled
        lda #enabled
        sta $1C0A          ; suppress actual NMI during enabled fallback test
        lda #(enabled * $80)
        sta $1C20
        stz $1C09
        ldx #127
        lda #2
:
        sta $1D00,x
        dex
        bpl :-
        ldx #63
        lda #0
:
        sta f:$7F23C0,x
        dex
        bpl :-
        lda #$23
        sta $1C27
        lda #$C0
        sta $1C26
        lda #$AB
        sta $1B
        sta $1C
        sta $1D
        sta $2C
        sta $2D
        lda #$40
        sta $40
        bit $40
        ldx #64
        ldy #$5A
        lda #$C0
        sec
        jsr bulk_attribute_bytes
        php
        cmp #$C0
        jne failed
        cpx #0
        jne failed
        cpy #$5A
        jne failed
        pla
        and #$C3
        cmp #$43
        jne failed
        lda $1C26
        jne failed
        lda $1C27
        cmp #$24
        jne failed
        lda $1C09
        cmp #64
        jne failed
        .repeat 5, var
            .if var < 3
                lda $1B+var
            .else
                lda $2C+var-3
            .endif
            cmp #$AB
            jne failed
        .endrepeat
        ldx #63
:
        lda f:$7F23C0,x
        cmp #$5A
        jne failed
        dex
        bpl :-
        ldx #127
:
        txa
        and #$20
        beq :+
        lda #2
        bra :++
:
        lda #3
:
        cmp $1D00,x
        jne failed
        dex
        bpl :---
    .endrepeat
    stz $1C0A
    lda #4
    sta $1C20
    lda #$23
    sta $1C27
    lda #$C0
    sta $1C26
    lda #$AD
    sta f:$7F23C1
    stz $1C09
    ldx #2
    ldy #$69
    jsr bulk_attribute_bytes
    lda f:$7F23C0
    cmp #$69
    jne failed
    lda f:$7F23E0
    cmp #$69
    jne failed
    lda f:$7F23C1
    cmp #$AD
    jne failed
    lda $1C09
    cmp #2
    jne failed
    lda $1C26
    jne failed
    lda $1C27
    cmp #$24
    jne failed
    stz $1C20
    stz $1C26
    stz $1C09
    lda #$25
    sta $1C27
    ldx #0                 ; original DEX loop: zero means 256 stores
    ldy #$96
    jsr bulk_attribute_bytes
    lda $1C09
    jne failed
    lda $1C26
    jne failed
    lda $1C27
    cmp #$26
    jne failed
    ldx #0
:
    lda f:$7F2500,x
    cmp #$96
    jne failed
    inx
    bne :-
    rts
register_ppudata_tests:
    lda #28
    sta $1C61
    stz $4200
    stz $1C20
    stz $1C18
    .repeat 2, register
        stz $1C09
        lda #$20
        sta $1C27
        lda #$10
        sta $1C26
        lda #2
        sta $1D00
        sta $1D40
        lda #$FF
        sta $1B20
        sta $1B21         ; stale generic address must not be consulted
        sta f:$7F2010
        lda #$40
        sta $40
        bit $40
        lda #$A5
        ldx #$34
        ldy #$5A
        lda #$A5         ; N=1, Z=0, V=1, C=1 at the store
        sec
        .if register = 0
            jsr io_stx_stub
        .else
            jsr io_sty_stub
        .endif
        php
        cmp #$A5
        jne failed
        cpx #$34
        jne failed
        cpy #$5A
        jne failed
        pla
        and #$C3
        cmp #$C1
        jne failed
        lda f:$7F2010
        .if register = 0
            cmp #$34
        .else
            cmp #$5A
        .endif
        jne failed
        lda $1C09
        cmp #1
        jne failed
        lda $1C26
        cmp #$11
        jne failed
        lda $1D00
        cmp #3
        jne failed
        lda $1D40
        cmp #3
        jne failed
    .endrepeat
    rts
repeat_run_tests:
    lda #27
    sta $1C61
    stz $1C8F
@run:
    stz $1C20
    stz $1C25
    stz $1C18
    stz $1C0A
    lda $1C8F
    beq @ready
    cmp #1
    bne @stride
    lda #$80
    sta $1C20
    lda #1
    sta $1C0A
    bra @ready
@stride:
    lda #4
    sta $1C20
@ready:
    lda #$AB
    sta $1C
    lda #$CD
    sta $1D
    lda #$F8
    sta $2C
    lda #$23
    sta $2D
    lda #$5E
    sta $1B
    stz $1C09
    ldx #7
    lda #0
@seed:
    sta f:$7F23F8,x
    dex
    bpl @seed
    ldx #8
    ldy #$25
    jsr bulk_repeat_bytes
    php
    sta $1C8E
    txa
    jne failed
    tya
    cmp #$25
    jne failed
    pla
    and #$C3
    cmp #2
    jne failed
    lda $1C8E
    cmp #$24
    jne failed
    lda $1C
    cmp #$AB
    jne failed
    lda $1D
    cmp #$CD
    jne failed
    lda $2C
    jne failed
    lda $2D
    cmp #$24
    jne failed
    cmp $1C27
    jne failed
    lda $1C8F
    cmp #2
    beq @ppu_stride
    lda $1C26
    jne failed
    bra @data_start
@ppu_stride:
    lda $1C26
    cmp #$1F
    jne failed
@data_start:
    lda $1C09
    cmp #8
    jne failed
    ldx #7
@data:
    lda f:$7F23F8,x
    cmp #$5E
    jne failed
    dex
    bpl @data
    inc $1C8F
    lda $1C8F
    cmp #3
    jcc @run
    stz $1C0A
    stz $1C20
    stz $1C09
    stz $2C
    lda #$25
    sta $2D
    ldx #0
    jsr bulk_repeat_bytes
    lda $2D
    cmp #$26
    jne failed
    lda $2C
    ora $1C09
    jne failed
    lda $1C
    cmp #$AB
    jne failed
    lda $1D
    cmp #$CD
    jne failed
    ldx #0
@page:
    lda f:$7F2500,x
    cmp #$5E
    jne failed
    inx
    bne @page
    rts

rect_run_tests:
    lda #26
    sta $1C61
    stz $1C20
    stz $1C25
    stz $1C18
    stz $1C8F
    ldx #15
    lda #0
@seed:
    sta f:$7F23BC,x
    dex
    bpl @seed
@run:
    ldx #127
@clear_flags:
    stz $1D00,x
    dex
    bpl @clear_flags
    stz $1C85
    stz $1C09
    lda #$BC
    sta $2C
    lda #$23
    sta $2D
    lda #1
    sta $1D
    lda #16
    sta $1C
    lda #$5A
    sta $1B
    ldy #$37
    jsr bulk_rect_bytes
    php
    sta $1C8E
    txa
    jne failed
    tya
    cmp #$37
    jne failed
    pla
    and #$C3
    cmp #2
    jne failed
    lda $1C8E
    cmp #$23
    jne failed
    lda $1C
    jne failed
    lda $2C
    cmp #$CC
    jne failed
    cmp $1C26
    jne failed
    lda $2D
    cmp #$23
    jne failed
    cmp $1C27
    jne failed
    lda $1C09
    cmp #16
    jne failed
    ldx #15
@data:
    lda f:$7F23BC,x
    cmp #$5A
    jne failed
    dex
    bpl @data
    ldx #127
@flags:
    lda $1C8F
    bne @zero
    txa
    and #$3F
    cmp #8
    bcc @one
    cmp #29
    beq @one
@zero:
    lda #0
    bra @compare
@one:
    lda #1
@compare:
    cmp $1D00,x
    jne failed
    dex
    bpl @flags
    inc $1C8F
    lda $1C8F
    cmp #2
    jcc @run
    ; Zero height is 256 bytes, not an empty run.
    ldx #0
    lda #0
@clear_page:
    sta f:$7F2500,x
    inx
    bne @clear_page
    stz $2C
    lda #$25
    sta $2D
    stz $1C
    stz $1C09
    lda #$3C
    sta $1B
    jsr bulk_rect_bytes
    lda $2D
    cmp #$26
    jne failed
    lda $2C
    ora $1C
    ora $1C09
    jne failed
    ldx #0
@page:
    lda f:$7F2500,x
    cmp #$3C
    jne failed
    inx
    bne @page
    ; Cross $23FF -> $2400 in both CIRAM mirroring modes. The destination
    ; changes physical table vertically, but aliases back to $2000 horizontally.
    stz $1C8F
@mirror_run:
    lda $1C8F
    sta $1C18
    ldx #7
@mirror_seed:
    lda #$22
    sta f:$7F2000,x
    sta f:$7F2400,x
    lda #0
    sta f:$7F23F8,x
    dex
    bpl @mirror_seed
    lda #$F8
    sta $2C
    lda #$23
    sta $2D
    lda #16
    sta $1C
    lda #$6C
    sta $1B
    jsr bulk_rect_bytes
    lda $2D
    cmp #$24
    jne failed
    lda $2C
    cmp #8
    jne failed
    ldx #7
@mirror_check:
    lda f:$7F23F8,x
    cmp #$6C
    jne failed
    lda $1C8F
    bne @horizontal
    lda f:$7F2400,x
    cmp #$6C
    jne failed
    lda f:$7F2000,x
    cmp #$22
    jne failed
    bra @mirror_next
@horizontal:
    lda f:$7F2000,x
    cmp #$6C
    jne failed
    lda f:$7F2400,x
    cmp #$22
    jne failed
@mirror_next:
    dex
    bpl @mirror_check
    inc $1C8F
    lda $1C8F
    cmp #2
    jcc @mirror_run
    stz $1C18
    ; Width two uses the original nested-loop fallback: two times three.
    lda #2
    sta $1D
    lda #3
    sta $1C
    stz $2C
    lda #$24
    sta $2D
    stz $1C09
    jsr bulk_rect_bytes
    lda $2C
    cmp #6
    jne failed
    cmp $1C09
    jne failed
    lda $1C
    jne failed
    rts

length_eligibility_tests:
    lda #25
    sta $1C61
    lda #$40
    sta $1B21
    lda #$0F
    sta $1CA1
    stz $1B22
    lda #$15
    sta $1B20
    jsl $C10000+dispatch_write
    lda $1CA1
    jne failed
    stz $0A16
    ldx #3
@disabled:
    stx $1B20
    jsl $C10000+dispatch_write
    inx
    inx
    inx
    inx
    cpx #19
    bne @disabled
    lda $0A16
    cmp #$CF                 ; reset/sweep flags survive disabled writes
    jne failed
    lda #$0F
    sta $1B22
    lda #$15
    sta $1B20
    jsl $C10000+dispatch_write
    lda $1CA1
    jne failed                ; enabling cannot restore eligibility
    stz $1B22
    ldx #3
@enabled:
    stx $1B20
    jsl $C10000+dispatch_write
    inx
    inx
    inx
    inx
    cpx #19
    bne @enabled
    lda $1CA1
    cmp #$0F
    jne failed
    lda #$0A
    sta $1B22
    lda #$15
    sta $1B20
    jsl $C10000+dispatch_write
    lda $1CA1
    cmp #$0A
    jne failed
    rts
unchanged_ppu_tests:
    lda #24
    sta $1C61
    stz $4200
    stz $1C20
    stz $1C18
    stz $1C8F
    lda #$A5
    sta f:$7F2010
@state:
    lda $1C8F
    sta $1D00
    eor #3                  ; aliases may have different publication states
    sta $1D40
    stz $1C85
    stz $1C09
    lda #$20
    sta $1C27
    lda #$10
    sta $1C26
    lda #$A5
    jsr io_write_stub
    lda $1D00
    cmp $1C8F
    jne failed
    lda $1C8F
    eor #3
    cmp $1D40
    jne failed
    lda $1C85
    jne failed
    lda $1C09
    cmp #1
    jne failed
    lda $1C26
    cmp #$11
    jne failed
    inc $1C8F
    lda $1C8F
    cmp #4
    bne @state
    rts
guarded_io_test:
    ; This checks a changed write on every guard invocation, including when
    ; the previous invocation wrote the same test value.
    lda #$5A
    sta f:$7F2010
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
    ; Same five bytes cross both the command-ring and PPU page boundaries
    ; without introducing new dirty work. Counters still count all writes.
    stz $1D07
    stz $1D08
    stz $1D47
    stz $1D48
    stz $1C85
    stz $1C09
    lda #$20
    sta $1C27
    lda #$FE
    sta $1C26
    ldx #61
    ldy #5
    jsr bulk_ring_bytes
    cmp #2
    jne failed
    lda $1D07
    ora $1D08
    ora $1D47
    ora $1D48
    ora $1C85
    jne failed
    lda $1C09
    cmp #5
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
    lda #64                ; verify the two physical tables after all wraps
    sta $1C8F
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
    ; The final eight stride-32 writes alias one palette entry; last wins.
    lda f:$7F3F00
    cmp #$9B
    jne failed
    ; Repeat the exact stride-32 command after clearing publication flags.
    ; The legacy path must recognize unchanged nametable bytes and avoid
    ; manufacturing dirty rows; this keeps its independent mutation control
    ; meaningful while increment-one traffic exercises the cached path above.
    ldx #127
    lda #0
@stride_clean:
    sta $1D00,x
    dex
    bpl @stride_clean
    stz $1C85
    stz $1C26
    lda #$20
    sta $1C27
    ldx #63
    ldy #0
    jsr bulk_ring_bytes
    lda $1C85
    jne failed
    ldx #127
@stride_flags:
    lda $1D00,x
    jne failed
    dex
    bpl @stride_flags
    stz $1C20
    rts
.ifdef EXPERIMENTAL_NATIVE_RING_CONSUMER
native_ring_consumer_tests:
    lda #31
    sta $1C61
    lda #$80
    sta $0100
    ; Five one-byte commands prove the four-command budget and retained fifth.
    ldx #0
    ldy #0
@commands:
    lda #$20
    sta $0545,x
    inx
    tya
    clc
    adc #$10
    sta $0545,x
    inx
    lda #0
    sta $0545,x
    inx
    lda #1
    sta $0545,x
    inx
    tya
    ora #$A0
    sta $0545,x
    inx
    iny
    cpy #5
    bne @commands
    ldx #4
    lda #0
@clear_destinations:
    sta f:$7F2010,x
    dex
    bpl @clear_destinations
    stz $06B6
    lda #25
    sta $06B7
    lda #$99
    sta $04
    stz $3E
    lda #4
    sta $F8
    jsr native_ring_consumer
    php
    lda #32
    sta $1C61
    plp
    jne failed
    cpx #20
    jne failed
    cpy #0
    jne failed
    lda $06B6
    cmp #20
    jne failed
    lda $04
    cmp #$99
    jne failed
    lda $F8
    jne failed
    lda #33
    sta $1C61
    ldx #0
@first_four:
    txa
    ora #$A0
    cmp f:$7F2010,x
    jne failed
    inx
    cpx #4
    bne @first_four
    lda f:$7F2014
    jne failed
    ; Bit 1 selects the one-command budget; consume the retained command.
    lda #34
    sta $1C61
    lda #2
    sta $3E
    jsr native_ring_consumer
    jne failed
    cpx #25
    jne failed
    lda $06B6
    cmp $06B7
    jne failed
    lda f:$7F2014
    cmp #$A4
    jne failed
    ; One command crosses the 64-byte ring boundary and writes both bytes.
    lda #35
    sta $1C61
    lda #$20
    sta $0545+61
    lda #$20
    sta $0545+62
    stz $0545+63
    lda #2
    sta $0545+0
    lda #$5A
    sta $0545+1
    lda #$5B
    sta $0545+2
    lda #61
    sta $06B6
    lda #3
    sta $06B7
    stz $3E
    jsr native_ring_consumer
    jne failed
    cpx #3
    jne failed
    lda f:$7F2020
    cmp #$5A
    jne failed
    lda f:$7F2021
    cmp #$5B
    jne failed
    ; Negative marker retains its destination in Y and stores the second
    ; buffered read, including ring wrap and the native read-buffer refill.
    lda #36
    sta $1C61
    lda #$20
    sta $0545+60
    stz $0545+61
    lda #$80
    sta $0545+62
    lda #$70
    sta $0545+63
    lda #60
    sta $06B6
    stz $06B7
    lda #$11
    sta $1C2A
    lda #$AA
    sta f:$7F2000
    lda #$BB
    sta f:$7F2001
    stz $70
    jsr native_ring_consumer
    jne failed
    cpx #0
    jne failed
    cpy #$70
    jne failed
    lda $70
    cmp #$AA
    jne failed
    lda $1C2A
    cmp #$BB
    jne failed
    lda $04
    cmp #$99
    jne failed
    ; A fade-budget WRITE must stop before a following READ that would alter
    ; $003E. This is the ordering invariant used by early palette preview.
    lda #40
    sta $1C61
    lda #$20
    sta $0545+60
    lda #$30
    sta $0545+61
    lda #4
    sta $0545+62
    lda #1
    sta $0545+63
    lda #$A6
    sta $0545
    lda #$20
    sta $0545+1
    stz $0545+2
    lda #$80
    sta $0545+3
    lda #$3E
    sta $0545+4
    lda #60
    sta $06B6
    lda #5
    sta $06B7
    lda #$0A
    sta $3E
    jsr native_ring_consumer
    lda $3E
    cmp #$0A
    jne failed
    lda $06B6
    cmp #1
    jne failed
    lda f:$7F2030
    cmp #$A6
    jne failed
    ; The consumer must not re-enable NMI inside either existing critical
    ; section. Test a real subsequent VBlank, not a read of write-only $4200.
    ; The third call proves the unguarded path really can enable NMI.
    .repeat 3, guard_case
    .scope
    lda #37 + guard_case
    sta $1C61
    phk
    pla
    sta $1CFC
    stz $4200
    lda $4210
    stz $1C8D
    stz $1C0A
    stz $1C83
    stz $06B6
    stz $06B7
    lda #$80
    sta $1C20
    .if guard_case = 0
        inc $1C0A
    .elseif guard_case = 1
        inc $1C83
    .endif
initial_blank:
    lda $4212
    bpl initial_blank
outside:
    lda $4212
    bmi outside
    jsr native_ring_consumer
wait_blank:
    lda $4212
    bpl wait_blank
wait_visible:
    lda $4212
    bmi wait_visible
    ; Emulation-mode RTI does not restore PB. The fixture's minimal interrupt
    ; handler returns into bank zero's identical high-ROM test code, so restore
    ; the saved test bank before calling any low-address replicated runtime.
    lda $1CFC
    pha
    pea .loword(bank_restored-1)
    rtl
bank_restored:
    stz $4200
    lda $1C8D
    .if guard_case < 2
        jne failed
    .else
        cmp #1
        jne failed
    .endif
    .endscope
    .endrepeat
    stz $1C0A
    stz $1C83
    stz $1C20
    stz $1C8D             ; independent later tests expect no observed NMI
    rts
.endif
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
    cpx #64
    bcc @unchanged_fill_row
    cpx #96
    bcc :+
@unchanged_fill_row:
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
    ; Four aligned pages use the complete-nametable dirty result.  This is
    ; the production transition shape targeted by the optional batch path.
    ldx #127
    lda #2
@clear_four_flags:
    sta $1D00,x
    dex
    bpl @clear_four_flags
    stz $1C85
    stz $1C26
    lda #$24
    sta $1C27
    lda #$6D
    sta $05
    ldx #4
    jsr bulk_fill_pages
    lda $1C27
    cmp #$28
    jne failed
    lda $1C26
    jne failed
    lda $1C85
    cmp #1
    jne failed
    ldx #0
@check_four_flags:
    lda #2
    cpx #32
    bcc :+
    cpx #64
    bcc @four_dirty
    cpx #96
    bcc :+
@four_dirty:
    lda #3
:
    cmp $1D00,x
    jne failed
    inx
    bpl @check_four_flags
    lda #$7F
    sta $09
    stz $07
    lda #$24
    sta $08
    ldy #0
@check_four_pages:
    lda [$07],y
    cmp #$6D
    jne failed
    iny
    bne @check_four_pages
    inc $08
    lda $08
    cmp #$28
    bne @check_four_pages
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
    cmp #$28            ; only CHR shadow and the two physical nametables
    bne @check_all
    rts
bulk_reader_tests:
    lda #15
    sta $1C61
    lda #64
    sta $1C12
    stz $1B50            ; direct fixture setup, unlike production mapper I/O
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
    ; End-of-page reads must keep both increments and remap at the boundary.
    .repeat 3, edge
    lda #$FD+edge
    sta $2A
    lda #$10
    sta $2B
    stz $1A
    jsr bulk_source_byte
    cmp #$FF
    jne failed
    lda $1C2A
    cmp #$FF
    jne failed
    lda $1C26
    cmp #($FF+edge) & $FF
    jne failed
    lda $1C27
    cmp #$10 + (edge > 0)
    jne failed
    .endrepeat
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
    sta f:$7F3F01        ; canonical backing for alias $3F21
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
    ; Source-address addition $7FFF + 1 sets V. Internal CHR pointer
    ; arithmetic must not leak its own overflow flag through the bulk ABI.
    lda #$FF
    sta $2A
    lda #$7F
    sta $2B
    lda #1
    sta $1A
    jsr bulk_source_byte
    php
    pla
    and #$40
    cmp #$40
    jne failed
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
.ifdef NAMETABLE_TEST
nametable_alias_tests:
    stz $41
    lda #22+NAMETABLE_TEST
    sta $1C61
    stz $1B20
    lda #$A0
    sta $1B21
    lda #NAMETABLE_TEST
    sta $1B22
    jsl $C10000+dispatch_write
    ; Each logical table gets a distinct value at the same tile offset.
    ldy #0
@write:
    tya
    asl
    asl
    ora #$20
    ldx #6
    jsr ppu_write_test
    lda #$15
    jsr ppu_write_test
    tya
    ora #$A0
    ldx #7
    jsr ppu_write_test
    iny
    cpy #4
    bne @write
    ldy #0
@read:
    tya
    asl
    asl
    ora #$20
    ldx #6
    jsr ppu_write_test
    lda #$15
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test
    jsr ppu_read_test
    lda $41
    bne @switched_expected
    tya
.if NAMETABLE_TEST = 0
    and #1                 ; vertical: [A,B,A,B], last writes are 2 and 3
    ora #$A2
.else
    and #2                 ; horizontal: [A,A,B,B], last writes are 1 and 3
    ora #$A1
.endif
    bra @compare
@switched_expected:
    tya
.if NAMETABLE_TEST = 0
    lsr
    ora #$A2               ; physical A2/B3 now appear horizontally
.else
    and #1
    asl
    ora #$A1               ; physical A1/B3 now appear vertically
.endif
@compare:
    cmp $1B24
    jne failed
    iny
    cpy #4
    bne @read
    lda $41
    bne @done
    inc $41
    ; Switching mappings retains physical contents and invalidates all rows.
    lda #2
    sta $1D00
    lda #3
    sta $1D7F
    stz $1B20
    lda #$A0
    sta $1B21
    lda #(NAMETABLE_TEST ^ 1)
    sta $1B22
    jsl $C10000+dispatch_write
    ldx #127
@invalidated:
    lda $1D00,x
    cmp #1
    jne failed
    dex
    bpl @invalidated
    lda $1C85
    cmp #1
    jne failed
    ; An odd-address $A001 write must not change the mapping.
    lda #1
    sta $1B20
    lda #NAMETABLE_TEST
    sta $1B22
    jsl $C10000+dispatch_write
    lda $1C18
    cmp #(NAMETABLE_TEST ^ 1)
    jne failed
    ldy #0
    jmp @read
@done:
    rts
.endif

palette_buffer_tests:
    lda #21
    sta $1C61
    stz $1C20
    stz $1C25
    stz $1C18
    ldy #0
@address:
    ; Distinct data below each palette address; aliases must not collapse
    ; the nametable address used for refilling the normal read buffer.
    tya
    tax
    eor #$80
    sta f:$7F2700,x         ; vertical mode: logical $2Fxx aliases $27xx
    lda #$3F
    ldx #6
    jsr ppu_write_test
    tya
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test
    tya
    eor #$80
    cmp $1C2A
    jne failed
    lda #$20
    ldx #6
    jsr ppu_write_test
    lda #0
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test
    tya
    eor #$80
    cmp $1B24
    jne failed
    iny
    bne @address
    rts

palette_alias_tests:
    lda #20
    sta $1C61
    stz $1C20
    stz $1C25
    ldy #0
@address:
    ; Every byte in the palette address page, including all eight mirrors.
    lda #$3F
    ldx #6
    jsr ppu_write_test
    tya
    jsr ppu_write_test
    tya
    and #$3F
    ldx #7
    jsr ppu_write_test
    ; Compute the expected canonical address independently in the fixture.
    tya
    and #$1F
    sta $40
    and #3
    bne :+
    lda $40
    and #$0F
    sta $40
:
    lda #$3F
    ldx #6
    jsr ppu_write_test
    lda $40
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test
    tya
    and #$3F
    cmp $1B24
    jne failed
    ; Read the alias too, not only the canonical backing byte.
    lda #$3F
    ldx #6
    jsr ppu_write_test
    tya
    jsr ppu_write_test
    ldx #7
    jsr ppu_read_test
    tya
    and #$3F
    cmp $1B24
    jne failed
    iny
    bne @address
    rts

transition_snapshot_tests:
    lda #19
    sta $1C61
    stz $1C20
    stz $1C78
    stz $1C79
    lda #0
    ldx #1
    jsr ppu_write_test
    lda $1CA0
    cmp #1
    jne failed
    ldx #0
@states:
    txa
    sta $1D00,x
    inx
    cpx #4
    bne @states
    jsr mask_test_write
    lda $1CA0
    cmp #2
    jne failed
    ldx #0
@verify:
    lda $1D00,x
    cmp transition_expected_states,x
    jne failed
    lda $1E80,x
    cmp transition_expected_required,x
    jne failed
    inx
    cpx #4
    bne @verify
    lda $1E9E
    ora $1E9F
    jne failed
    ; A pattern-half change requires a fresh conversion even for clean rows.
    lda #1
    sta $1CA0
    lda #$10
    sta $1C20
    stz $1D00
    jsr mask_test_write
    lda $1D00
    cmp #1
    jne failed
    lda $1E80
    cmp #1
    jne failed
    stz $1CA0
    stz $1C20
    rts
transition_expected_states:
    .byte 0,1,2,1
transition_expected_required:
    .byte 0,1,1,1

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
