; Paired execution of the real legacy/generated direct stubs, no game assets.
.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
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
    lda #1
    sta $420D
    clear_wram_dma
    jml $C30000+initialize
initialize:
    rep #$30
    .a16
    .i16
    lda #0
    tcd
    ldx #$01FF
    txs
    ldx a:$0602
    sep #$20
    .a8
    lda #$83
    pha
    plb
    lda cases,x
    sta a:$07F9
    lda cases+1,x
    sta a:$07FA
    lda cases+2,x
    sta a:$0606
    lda cases+3,x
    sta a:$0607
    lda cases+4,x
    sta a:$0A15
    lda cases+5,x
    sta a:$0A16
    lda cases+6,x
    sta a:$1CA1
    lda #1
    sta a:$1C0A
    lda #$C3
    sta a:$1C02
    sta a:$1C03
    lda #0
    sta a:$1C20
    ldx #20
    lda #$AA
@apu:
    sta a:$0A00,x
    dex
    bpl @apu
    sta a:$0A17
    rep #$20
    .a16
    lda #$1234
    tcd
    sep #$30
    .a8
    .i8
    sec
    xce
    lda a:$0608
    bne fast
    ldx #$34
    ldy #$56
    lda a:$0607
    pha
    lda a:$0606
    plp
legacy_call:
    jsr legacy_stub
legacy_done:
    bra snapshot
fast:
    ldx #$34
    ldy #$56
    lda a:$0607
    pha
    lda a:$0606
    plp
fast_call:
    jsr fast_stub
fast_done:
    bra snapshot
snapshot:
    sta f:$7E3000
    php
    pla
    sta f:$7E3001
    txa
    sta f:$7E3002
    tya
    sta f:$7E3003
    phb
    pla
    sta f:$7E3004
    phd
    pla
    sta f:$7E3005
    pla
    sta f:$7E3006
    phk
    pla
    sta f:$7E3007
    tsx
    txa
    sta f:$7E3008
    clc
    xce
    rep #$10
    cld
    .i16
    ldx #0
@packet:
    lda a:$0A00,x
    sta f:$7E3009,x
    inx
    cpx #24
    bne @packet
    lda a:$1CA1
    sta f:$7E3021
    lda a:$0608
    bne compare
    ldx #0
@save:
    lda f:$7E3000,x
    sta f:$7E3100,x
    inx
    cpx #34
    bne @save
    inc a:$0608
    jmp initialize
compare:
    ldx #0
@byte:
    lda f:$7E3000,x
    cmp f:$7E3100,x
    bne failed
    inx
    cpx #34
    bne @byte
    ldy #0
    ldx a:$0604
@record:
    ; DB becomes 7E only for reading the host-visible result buffer.
    lda #$7E
    pha
    plb
    lda a:$3000,y
    sta f:$7F0000,x
    iny
    inx
    cpy #34
    bne @record
    stx a:$0604
    stz a:$0608
    rep #$20
    .a16
    lda a:$0602
    clc
    adc #7
    sta a:$0602
    cmp #cases_end-cases
    bcc next
    sep #$20
    .a8
    lda #1
    sta a:$1C60
    bra alive
next:
    jmp initialize
failed:
    lda #$EE
    sta a:$1C60
alive:
    lda #0
    pha
    plb
@active:
    lda $4212
    bmi @active
@blank:
    lda $4212
    bpl @blank
    inc a:$1C62
    bne @active
    inc a:$1C63
    bra @active
cases:
    .include "direct_apu_cases.inc"
cases_end:
interrupt:
    rti
.segment "HEADER"
    .byte "RCR DIRECT APU TEST  "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
