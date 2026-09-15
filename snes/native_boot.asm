; Experimental CPU integration cartridge. Original PRG runs as 65C816 code.
.setcpu "65816"
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
    stz $420B
    stz $420C
.ifdef EXPERIMENTAL_FASTROM
    ; Opt-in timing regression until full-game validation is complete.
    ; Program/runtime banks C0-C8 and DB mirrors 81-88 are FastROM-capable.
    ; Select the real SNES 6-master-clock ROM timing (not emulator overclocking).
    lda #1
    sta $420D
.endif
    stz $212C
    stz $212D
    stz $2130
    stz $2131
    lda #4
    sta $2133
    ldx #0
@clear:
    lda #0
    sta f:$7E0000,x
    sta f:$7F0000,x
    inx
    bne @clear
    ldx #0
    lda #$FF
@cache:
    sta $1DA0,x
    inx
    cpx #24
    bne @cache
    stz $2105
    stz $2106
    stz $210B
    stz $210C
    stz $2123
    stz $2124
    stz $2125
    stz $212E
    stz $212F
    lda #$20
    sta $2107
    lda #2
    sta $2101
    stz $210D
    stz $210D
    lda #$FF
    sta $210E
    sta $210E
    jsr spc_upload
    bcc :+
    lda #$EE
    sta $1C0B
:
    lda #$00                ; legacy engine bit 5 clear: NES mono on both outputs
    sta $0A16
    lda #$4F
    sta $1C00
    lda #$FF
    sta $1C01
    lda #$C7
    sta $1C02
    sta $1C03              ; current program bank
    lda #12
    sta $1C16              ; MMC3 R6
    lda #13
    sta $1C17              ; MMC3 R7
    lda #$1F
    sta $2121
    stz $2121
    lda #$E0
    sta $2122
    lda #$03
    sta $2122
    lda #$0F
    sta $2100
    sep #$30
    .i8
    lda #$87
    pha
    plb
    sec
    xce
    jml $C7FF76
nmi:
    ; Emulation-mode interrupt stack has the same three-byte shape as NES.
    ; All game banks replicate the runtime, so interrupted helper PCs remain valid.
    stz $4200
    pha
    lda $4210
    inc $1C0A
    inc $1C04
    bne :+
    inc $1C05
:
    ; Bounded prepared-data consumer runs on every game NMI, before game code.
    jsr publish_video
    pla
    jml [$1C00]
publish_video:
    php
    pha
    phx
    phy
    phd
    phb
    clc
    xce
    rep #$30
    .a16
    .i16
    lda #$1E00
    tcd
    sep #$20
    .a8
    lda #0
    pha
    plb
    jsr native_video
    jsr spc_frame
    bcc :+
    lda #$EE
    sta $1C0B
:
    lda #$00
    sta $0A16
    sep #$30
    .a8
    .i8
    sec
    xce
    plb
    pld
    ply
    plx
    pla
    plp
    rts
video_prepare_bridge:
    ; Producer called by hardware adapter with E=1 and NMI disabled.
    php
    pha
    phx
    phy
    phd
    phb
    clc
    xce
    rep #$30
    .a16
    .i16
    lda #$1E00
    tcd
    sep #$20
    .a8
    lda #0
    pha
    plb
    rep #$20
    .a16
    jsr native_prepare
    sep #$30
    .a8
    .i8
    sec
    xce
    plb
    pld
    ply
    plx
    pla
    plp
    rtl
irq:
    pha
    lda $4211
    pla
    ; Until the IRQ timing adapter is installed, CPU proof keeps IRQ disabled.
    rti
native_interrupt:
    rti
.i16
.include "native_video.asm"
.include "native_prepare.asm"
.include "native_audio.asm"
.segment "HEADER"
    .byte "RCR NATIVE CPU PROOF "
.ifdef EXPERIMENTAL_FASTROM
    .byte $31
.else
    .byte $21
.endif
    .byte $00, $0B, $00, $01, $00, $00
    .word $FFFF, $0000
.segment "VECTORS"
    .word 0,0,native_interrupt,native_interrupt,native_interrupt,native_interrupt,0,native_interrupt
    .word 0,0,irq,0,nmi,nmi,reset,irq
