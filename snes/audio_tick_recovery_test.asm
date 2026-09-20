; Asset-free recurring E=1 scheduler probe, NOT the game's scheduler.
; Real NMI epochs; timer IRQ at80; direct recovery after hardware masking.
.setcpu "65816"
.a16
.i16
.segment "CODE"
.macro save_context
    php
    pha
    phx
    phy
    phd
    phb
    cld
    pea $0000
    pld
    lda #0
    pha
    plb
.endmacro
.macro restore_context
    plb
    pld
    ply
    plx
    pla
    plp
.endmacro
reset:
    sei
    clc
    xce
    rep #$38
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
    lda #4
    sta $2133
    ldx #$0200
clear:
    stz $1800,x
    dex
    bpl clear
    lda #$FC
    sta $1801
    lda #$FF
    sta $1802
    lda #80
    sta $4209
    stz $420A
    sep #$30
    .i8
    sec
    xce
    lda $4210
    lda #$80
    sta $4200
    cli
loop:
    lda f:$001810
    beq :+
    jmp finished
:
    lda f:$001806
    cmp f:$00180F
    beq loop
    sta f:$00180F
    ; Wait until the new epoch's active scanout. No clock is synthesized.
wait_active:
    lda f:$004212
    bmi wait_active
.if MODE > 0
wait_mask:
    jsr beam
    cmp #40
    bcc wait_mask
    lda #0
    sta f:$004200
wait_resume:
    jsr beam
    cmp #RESUME_LINE
    bcc wait_resume
.endif
    ; Main-thread sentinels including accumulator B and decimal/carry.
    lda #$12
    xba
    lda #$34
    tcd
    lda #$7E
    pha
    plb
    lda #$AB
    xba
    lda #$CD
    ldx #$78
    ldy #$BC
    sed
    sec
.if MODE > 0
    jsr recover
.endif
.if MODE = 0 .or RESUME_LINE < 80
    wai
.endif
    ; Preserve observations without using DP or altering A/X/Y first.
    php
    sta f:$7E1A00
    xba
    sta f:$7E1A01
    xba
    txa
    sta f:$7E1A02
    tya
    sta f:$7E1A03
    pla
    sta f:$7E1A04
    phb
    pla
    sta f:$7E1A05
    tdc
    sta f:$7E1A06
    xba
    sta f:$7E1A07
    xba
    tsx
    txa
    sta f:$7E1A08
    cld
    lda #0
    pha
    plb
    pea $0000
    pld
    ; Re-entering a safe exit must not replay an already-served job.
.if MODE > 0
    jsr recover
.endif
    jmp loop
finished:
    sei
    lda #0
    sta f:$004200
halt:
    bra halt

beam:
    lda f:$00213F
    lda f:$002137
    lda f:$00213D
    rts

; Called only after the emulated critical section has released ownership.
; NMI remains disabled until restore; old deferred work is never marked served
; without actually executing service. At VBlank, NMI recovers the old epoch.
recover:
    save_context
    sei
    stz $4200
.ifndef OMIT_RECOVERY
    lda $1800
    beq enable
    jsr beam
    cmp #80
    bcc enable
    cmp #240
    bcs enable
    lda #2
    jsr service
.endif
enable:
    lda $1810
    bne recovered
    lda $1800
    beq nmi_only
    lda #$A0
    bra set_enable
nmi_only:
    lda #$80
set_enable:
    sta $4200
recovered:
    restore_context
.ifdef CLOBBER_X
    ldx #0
.endif
    rts

nmi:
    save_context
    stz $4200
    lda $4210
    inc $1806
    lda $1800
    beq new_epoch
    lda #3
    jsr service
new_epoch:
    lda $1806
    cmp #33
    bcc schedule
    lda #1
    sta $1810
    restore_context
    rti
schedule:
    inc $1801
    bne :+
    inc $1802
:
    lda $1801
    sta $1803
    lda $1802
    sta $1804
    lda #1
    sta $1800
    lda $4211
    lda #$A0
    sta $4200
    restore_context
    rti
irq:
    save_context
    lda $4211
    sta $180A
    lda $4211
    sta $180B
    stz $4200
    inc $1805
    lda #1
    jsr service
    lda #$80
    sta $4200
    restore_context
    rti

service:
    sta $180C
    lda $1800
    beq no_job
.ifndef DUPLICATE_SERVICE
    stz $1800
.endif
    ldx $1809
    cpx #32
    bcs overflow
    lda $1803
    sta $1900,x
    lda $1804
    sta $1920,x
    jsr beam
    sta $1940,x
    lda $213D
    and #1
    sta $1960,x
    lda $180C
    sta $1980,x
    inc $1809
    ; Deliberately destructive stand-in for a sound driver: surrounding entry
    ; paths, not a polite spy, must preserve the interrupted main context.
    lda #$55
    ldx #$11
    ldy #$22
    sec
    rts
overflow:
    inc $1808
no_job:
    rts
.segment "HEADER"
    .byte "RCR AUDIO TICK TEST  "
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,halt,halt,halt,halt,0,halt
    .word 0,0,halt,0,halt,nmi,reset,irq
