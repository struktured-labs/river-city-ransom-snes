; Replace FD8E..FDA2 after the original LDX #8 and strobe writes.
; E=1, A8/X8, original DP/DB. Existing SNES mapping/latching is untouched.
; Consume cached bits without sixteen generic I/O transactions. A high strobe
; still reads the live physical ports. NMI is masked for this bounded loop.
native_joypad_poll:
    stz $4200
    lda #$1B
    xba                     ; same hidden B as generic dispatch_read
    lda a:$1C82
    bne @live
@cached:
    sec
    ror a:$1C80
    rol $EE
    sec
    ror a:$1C81
    rol $EF
    dex
    bne @cached
    lda $EF
    and #1                  ; final port-2 read, before its two shifts
    sta a:$1B24
    lsr $05                 ; original eight ROLs leave original bit0 in C
    stz $04
    stz $05
    bra @finish
@live:
    lda $4016
    and #1
    lsr
    rol $EE
    lsr
    rol $04
    lda $4017
    and #1
    sta a:$1B24
    lsr
    rol $EF
    lsr
    rol $05
    dex
    bne @live
@finish:
    lda #$17
    sta a:$1B20
    lda #$40
    sta a:$1B21
    lda #0                  ; original last shifted read is zero; X=0
    php
    lda a:$1C0A
    ora a:$1C83
    bne @return
    load_interrupt_enable
    beq @return
    sta $4200
@return:
    plp
    lda #0
    jmp $FDA3
