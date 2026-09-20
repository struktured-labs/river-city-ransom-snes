.setcpu "65816"
.include "wram_clear.inc"
.a8
.i16
.segment "CODE"
reset:
    jml $C00000+main
main:
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
    stz $4200
    stz $420B
    stz $420C
    lda #$80
    sta $2100
    clear_wram_dma
    stz $2102
    stz $2103
    ldx #544
    lda #$A5
poison:
    sta $2104
    dex
    bne poison
generation:
    ; Every64th generation is hidden and changes the supposedly static tail.
    ; The full hidden upload must publish those changes before visible updates.
    lda $0300
    and #63
    bne visible
    lda #1
    sta $1CA0
    ldx #256
tail_seed:
    txa
    eor $0300
    sta f:$7E5000,x
    inx
    cpx #544
    bne tail_seed
    bra seed_begin
visible:
    stz $1CA0
seed_begin:
    ldx #0
seed:
    txa
    eor $0300
    sta f:$7E5000,x
    inx
    cpx #256
    bne seed
    ; Re-enter at C0 so JSR5100 executes actual emitted production bytes.
    lda #$AB
    ldx #123
    ldy #456
    jsr $5100
    pha
    lda #1
    sta $1C61
    pla
    cmp #$80
    bne failed_jump
    cpx #544
    bne failed_jump
    cpy #456
    bne failed_jump
    lda $1BF0
    cmp #1
    bne failed_jump
    ; A1T increments by the actual DMA size, even though DAS becomes zero.
    ldx $4302
    lda $0300
    and #63
    beq full_count
    cpx #$5100
    bne failed_jump
    bra count_ok
full_count:
    cpx #$5220
    bne failed_jump
count_ok:
    lda #2
    sta $1C61
    stz $2102
    stz $2103
    ldx #0
check:
    lda $2138
    sta f:$7E6000,x
    cmp f:$7E5000,x
    bne failed_jump
    inx
    cpx #544
    bne check
    inc $1C62
    bne :+
    inc $1C63
:
    inc $0300
    beq complete
    jmp generation
failed_jump:
    jmp failed
complete:
    rep #$20
    .a16
    lda $1C62
    sta $0302
    sep #$20
    .a8
    lda #1
    sta $1C60
    stz $1C61
    stz $1C06
done:
    lda $4212
    bmi done
wait_blank:
    lda $4212
    bpl wait_blank
    inc $1C62
    bne done
    inc $1C63
    bra done
failed:
    lda #$EE
    sta $1C60
    bra done
irq:
    rti
.segment "HEADER"
.byte "RCR EARLY HALF TEST "
.byte $31,$00,$0B,$00,$01,$33,$00
.word $FFFF,$0000
.segment "VECTORS"
.word 0,0,irq,irq,irq,irq,0,irq
.word 0,0,irq,irq,irq,irq,reset,irq
