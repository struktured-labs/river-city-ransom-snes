; CV1-style hardware polling, adapted to RCR's cached NES input ABI.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export enable_poll, mask_interrupts, read_pads, rumble_latch, rumble_finish

enable_poll:
    php
    pha
    ora #1
    sta $4200
    pla
    plp
    rts
mask_interrupts:
    php
    pha
    lda #1
    sta $4200
    pla
    plp
    rts

; Do not mistake the short pre-auto-read VBlank interval for completion.
; This is called with interrupts already masked and preserves X/Y.
wait_poll:
    lda $4212
    bpl @busy
    phx
    ldx #255
@guard:
    dex
    bne @guard
    plx
@busy:
    lda $4212
    and #1
    bne @busy
    rts

read_pads:
    lda $22
    and #1
    tax
    lda a:$1C82
    stx a:$1C82
    cpx #0
    bne @done
    and #1
    beq @done
    jsr wait_poll
    ; JOY high bytes are B,Y,Select,Start,Up,Down,Left,Right MSB first.
    ; RCR's cached serial shift register consumes those in LSB-first order.
    lda $4219
    ldy #8
@p1:
    asl
    ror a:$1C80
    dey
    bne @p1
    lda $421B
    ldy #8
@p2:
    asl
    ror a:$1C81
    dey
    bne @p2
    lda $4218
    bpl @p2jump
    lda a:$1C80
    ora #3
    sta a:$1C80
@p2jump:
    lda $421A
    bpl @done
    lda a:$1C81
    ora #3
    sta a:$1C81
@done:
    jmp $6B10

; A completely separate serial transaction, after auto-read has finished.
; Called only when the existing rumble scheduler actually sends a packet.
rumble_latch:
    php
    pha
    phx
    phy
    ; Prevent the next auto-read starting halfway through this transaction.
    ; Any read already in progress must finish before we latch manually.
    stz $4200
    jsr wait_poll
    lda #1
    sta $4016
    nop
    nop
    stz $4016
    nop
    nop
    ldy #16
@clock:
    lda $4016
    dey
    bne @clock
    ply
    plx
    pla
    plp
    sta f:$7EF807
    rts

rumble_finish:
    sta f:$004201
    php
    pha
    lda #1
    sta $4200
    pla
    plp
    rts
