; A8/X16/Y16, DB=0, DP=1E00. Original row DMA trigger is replaced by JSR here.
; Transfer the original row first. A ready mirror may follow, using its OWN
; immutable stage, only if the existing byte budget and row_room admit it.
; No new persistent metadata, no skipped mirror, no relaxed beam deadline.
.setcpu "65816"
.a8
.i16
.segment "CODE"
.export entry
entry:
    sta $420B
    php
    rep #$20
    .a16
    pha
    phx
    phy
    lda $1E
    cmp #64
    beq :+
    jmp done
:
    ; Original row has not yet been debited by its caller.
    lda $1A
    cmp #128
    bcs :+
    jmp done
:
    lda $1C18
    and #1
    beq vertical
    txa
    eor #$0020
    bra alias_index
vertical:
    txa
    eor #$0040
alias_index:
    tax
    sep #$20
    .a8
    lda $1D00,x
    and #2
    bne :+
    jmp done
:
    jsr $87E4
    bcs :+
    jmp done
:
    ; Same ownership/age handling as the original scalar consumer.
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
    sta $1C85
:
    rep #$20
    .a16
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
    lda #64
    sta $4305
    sep #$20
    .a8
    lda #$7E
    sta $4304
    lda #1
    sta $420B
    rep #$20
    .a16
    lda $1A
    sec
    sbc #64
    sta $1A
done:
    rep #$20
    .a16
    ply
    plx
    pla
    plp
    rts
