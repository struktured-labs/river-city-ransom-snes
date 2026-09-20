; E=1/A8/X8 only, in already-masked graphics work. No guest NMI reentrancy.
; $1B87 pending, $1B88/89 collected, $1B8A/B served, $1B8C overflow fault.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export collect_vblank, ring_read_long, ring_read_short, queued_return, queued_entry
collect_vblank:
    php
    pha
    lda a:$1C0A
    cmp #1
    bne done
    lda a:$0100
    and #$C0
    cmp #$C0
    bne done
    lda a:$1C20
    bpl done
    ; Reading the actual flag acknowledges this event. Do NOT change the
    ; active native/audio event ID until its predecessor finishes its exit.
    lda $4210
    bpl done
    lda a:$1B87
    cmp #$FF
    beq overflow
    inc a:$1B87
    inc a:$1B88
    bne done
    inc a:$1B89
    bra done
overflow:
    lda #1
    sta a:$1B8C
done:
    pla
    plp
    rts

ring_read_long:
    jsr collect_vblank
    lda f:$000545,x
    rtl
ring_read_short:
    jsr collect_vblank
    lda a:$0545,x
    rts

queued_return:
    ; The original saved Y/X/A and P/PCL/PCH frame remain intact here.
    jsr collect_vblank
    lda a:$1B87
    beq ordinary
    lda a:$1C0A
    cmp #1
    bne ordinary
    dec a:$1B87
    inc a:$1B8A
    bne :+
    inc a:$1B8B
:
    dec a:$1C0A
    pla
    tay
    pla
    tax
    pla
    ; Tail-chain against the SAME original interrupt frame. The old event's
    ; sound publication has completed; the native entry now assigns a new ID.
    jmp queued_entry
ordinary:
    ; Replay the three bytes displaced by the trampoline, then retain the
    ; existing coroutine-stack test and ordinary VBlank-exit wait policy.
    pla
    tay
    pla
    jmp RETURN_BODY

queued_entry:
    stz $4200
    pha
    ; The collected flag was acknowledged already. Skipping the native
    ; $4210 read avoids eating a newer event between collection and service.
    jml NMI_AFTER_ACK
