.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.ifndef PENDING_NMI
PENDING_NMI=0
.endif
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
    lda #4
    sta $2133
    clear_wram_dma
    jml $C10000+initialize
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
    lda #$80+SOURCE_BANK
    pha
    plb
    lda cases,x
    sta a:$00FC
    sta a:$1C08
    eor #$80
    sta a:$1C19
    lda cases+1,x
    sta a:$00FD
    lda cases+2,x
    sta a:$00FB
    lda cases+3,x
    sta a:$0607
    lda cases,x
    and #1
    sta a:$1C0A
    lda cases,x
    lsr
    and #1
    sta a:$1C83
    lda cases,x
    and #4
    sta a:$1CBB
    lda #$C0+SOURCE_BANK
    sta a:$1C02
    sta a:$1C03
    lda #$55
    sta a:$00FF
    stz a:$1C20
    stz a:$0609
.if PENDING_NMI
    lda #$80
    sta a:$1C20
    lda #<interrupt_return
    sta a:$0610
    lda #>interrupt_return
    sta a:$0611
    ; A real fresh hardware edge, masked until the helper's normal policy
    ; permits it. Do not read $4210 after waiting for the new edge.
    stz $4200
@active_before_edge:
    lda $4212
    bmi @active_before_edge
    lda $4210
@fresh_edge:
    lda $4212
    bpl @fresh_edge
.endif
    sep #$30
    .i8
    sec
    xce
    jml $C00000+SOURCE_BANK*$10000+caller
caller:
    lda a:$0608
    bne fast
    ldx #$5A
    ldy #$A5
    lda a:$0607
    pha
    lda #$98
    plp
legacy_call:
    jsr legacy_restore
legacy_done:
    stz $4200
    bra snapshot
fast:
    ldx #$5A
    ldy #$A5
    lda a:$0607
    pha
    lda #$98
    plp
fast_call:
    jsr native_bank_restore
fast_done:
    stz $4200
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
    lda a:$00FF
    sta f:$7E3009
    lda a:$00FB
    sta f:$7E300A
    lda a:$00FC
    sta f:$7E300B
    lda a:$00FD
    sta f:$7E300C
    lda a:$1C16
    sta f:$7E300D
    lda a:$1C17
    sta f:$7E300E
    lda a:$1C19
    sta f:$7E300F
    lda a:$1C02
    sta f:$7E3010
    lda a:$1C03
    sta f:$7E3011
    lda a:$1C08
    sta f:$7E3012
    lda a:$1CBB
    sta f:$7E3013
    lda a:$1C83
    sta f:$7E3014
    lda a:$1B20
    sta f:$7E3015
    lda a:$1B21
    sta f:$7E3016
    lda a:$1B22
    sta f:$7E3017
    lda a:$0609
    sta f:$7E3018
    clc
    xce
    rep #$10
    .i16
    lda a:$0608
    bne compare
    ldx #0
@save:
    lda f:$7E3000,x
    sta f:$7E3100,x
    inx
    cpx #25
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
    cpx #25
    bne @byte
    lda #$7E
    pha
    plb
    ldy #0
    ldx a:$0604
@record:
    lda a:$3000,y
    sta f:$7F0000,x
    iny
    inx
    cpy #25
    bne @record
    stx a:$0604
    stz a:$0608
    rep #$20
    .a16
    lda a:$0602
    clc
    adc #4
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
; Exact original FF29 instruction sequence, substituting the same generated
; mapper stubs as the port for its five STA $8000/$8001 instructions.
legacy_restore:
    lda #0
    sta $FF
    lda #6
    sta $FF
    jsr select_stub
    lda $FC
    jsr data_stub
    lda #7
    sta $FF
    jsr select_stub
    lda $FD
    jsr data_stub
    lda #0
    sta $FF
    lda $FB
    jsr select_stub
    rts
cases:
    .include "bank_restore_cases.inc"
cases_end:
interrupt:
    pha
    lda $4210
    inc a:$0609
    lda a:$1C02
    sta a:$0612
    pla
    jml [$0610]
interrupt_return:
    rti
.segment "HEADER"
    .byte "RCR BANK RESTORE TEST"
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
