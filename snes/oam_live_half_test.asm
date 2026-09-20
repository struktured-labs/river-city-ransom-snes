.setcpu "65816"
.include "wram_clear.inc"
.include "oam_live_half.inc"
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
    stz $4200
    stz $420B
    stz $420C
    lda #$80
    sta $2100
    clear_wram_dma
    ; Poison all physical OAM; initialization must replace every byte.
    stz $2102
    stz $2103
    ldx #544
    lda #$A5
poison:
    sta $2104
    dex
    bne poison
    ; Seed unused staging entries exactly as the production delta producer:
    ; hidden Y=240, everything else zero, including the entire high table.
    ldx #257
    lda #240
hidden:
    sta f:$7E5000,x
    inx
    inx
    inx
    inx
    cpx #512
    bcc hidden
generation:
    ; Every generation changes all 256 live bytes, including the last slot.
    ldx #0
seed:
    txa
    eor $0300
    sta f:$7E5000,x
    inx
    cpx #256
    bne seed
    stz $2102
    stz $2103
    stz $4300
    lda #4
    sta $4301
    ldx #$5000
    stx $4302
    lda #$7E
    sta $4304
    select_oam_transfer_size
    lda #1
    sta $1C61
    lda $0300
    beq first_count
.ifdef EXPERIMENTAL_OAM_LIVE_HALF
    cpx #256
.else
    cpx #544
.endif
    bne failed
    bra count_ok
first_count:
    cpx #544
    bne failed
count_ok:
    stx $4305
    lda #1
    sta $420B
    complete_oam_transfer
    lda #2
    sta $1C61
    stz $2102
    stz $2103
    ldx #0
check:
    lda $2138
    sta f:$7E6000,x
    cmp f:$7E5000,x
    bne failed
    inx
    cpx #544
    bne check
    inc $1C62
    bne :+
    inc $1C63
:
    inc $0300
    bne generation_jump
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
generation_jump:
    jmp generation
failed:
    lda #$EE
    sta $1C60
    bra done
irq:
    rti
.segment "HEADER"
.byte "RCR OAM HALF TEST    "
.byte $31,$00,$0B,$00,$01,$33,$00
.word $FFFF,$0000
.segment "VECTORS"
.word 0,0,irq,irq,irq,irq,0,irq
.word 0,0,irq,irq,irq,irq,reset,irq
