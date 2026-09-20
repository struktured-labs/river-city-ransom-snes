; Experimental CPU integration cartridge. Original PRG runs as 65C816 code.
.setcpu "65816"
.a8
.i16
.include "wram_clear.inc"
.include "apu_length_gate.inc"
.include "early_audio_abi.inc"
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
    clear_wram_dma
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
    ; Bounded prepared-data consumer normally runs before game code. During a
    ; forced-blank transition, the game-first experiment drains it after the
    ; original interrupt and latches the final unblank for a real VBlank.
.ifdef EXPERIMENTAL_TRANSITION_GAME_FIRST
    lda a:$1CA0
    beq @publish_before_game
    lda a:$1CEF
    beq @published_or_deferred
@publish_before_game:
.endif
    jsr publish_video
.ifdef EXPERIMENTAL_TRANSITION_GAME_FIRST
    stz a:$1CEF
@published_or_deferred:
.endif
.ifdef EXPERIMENTAL_DEFERRED_GAME_NMI
    ; During a marked visible-game iteration, let the already-running main
    ; thread finish its exact E2A2 camera calculation before entering RCR's
    ; original NMI body.  The camera hook recreates an emulation interrupt
    ; frame and dispatches that retained body immediately after publication.
    lda a:$1CE0
    bne @deferred_fallback
    lda a:$0100
    and #$C0
    cmp #$C0
    bne @game_nmi
    lda a:$0107
    bmi @game_nmi
    lda a:$1CA0
    beq :+
    stz a:$1CEB
    bra @game_nmi
:
    lda a:$1CEB
    beq @game_nmi
    lda a:$1CE1
    beq @game_nmi
    lda #1
    sta a:$1CE0
    inc a:$1CE2
    bne :+
    inc a:$1CE3
:
@deferred_late_vblank:
    ; Keep the main-loop phase locked near the frame boundary, but resume at
    ; line 250 instead of burning the final twelve VBlank lines.  $213F resets
    ; the OPVCT read flip-flop; after wrap, the second $213D read exposes V bit
    ; 8 so a missed low-byte threshold cannot deadlock the retained interrupt.
    lda $213F
    lda $2137
    lda $213D
    sta a:$1CEC
    lda $213D
    and #1
    bne @deferred_late_vblank_done
    lda a:$1CEC
.ifdef DEFERRED_RESUME_LINE
    ; Optional phase policy: the bounded publisher has already completed.
    ; Do not discard its savings by waiting until the old line250 threshold.
    .assert DEFERRED_RESUME_LINE >= 240 .and DEFERRED_RESUME_LINE <= 250, error, "Deferred resume outside VBlank policy"
    cmp #DEFERRED_RESUME_LINE
.else
    cmp #250
.endif
    bcc @deferred_late_vblank
@deferred_late_vblank_done:
.ifdef EXPERIMENTAL_EARLY_DEFERRED_AUDIO
    ; The publisher and the late-VBlank phase guard have finished. Service
    ; sound now, before allowing a variable-length camera calculation to run.
    jsl $C10000+EARLY_AUDIO_ENTRY
.endif
    dec a:$1C0A
    ; Emulation RTI restores P/PC but not PB.  Enter the untouched original
    ; RTI opcode at F1D8 through the tracked current program bank so the
    ; interrupted main PC resumes in its actual replicated bank, not bank 00.
    lda #$D8
    sta a:$1CE8
    lda #$F1
    sta a:$1CE9
    lda a:$1C02
    sta a:$1CEA
    ; Keep NMI masked while the retained main thread finishes inside the tail
    ; of this VBlank.  Re-enabling $4200 while $4210 is still asserted can
    ; immediately retrigger NMI and consume the camera head start.  The camera
    ; hook dispatches the retained game interrupt, whose normal return restores
    ; the saved interrupt policy after VBlank has ended.
    stz $4200
    pla
    jml [$1CE8]
@deferred_fallback:
    ; A second VBlank before the marked camera is a measurable failure, not a
    ; license to overwrite a retained game interrupt.  Service the old job on
    ; this real interrupt frame and leave the current event unscheduled.
    stz a:$1CE0
    inc a:$1CE4
    bne :+
    inc a:$1CE5
:
    inc a:$1CE6
    bne @game_nmi
    inc a:$1CE7
@game_nmi:
.endif
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
.ifdef EXPERIMENTAL_FAST_PUBLISHER
    ; Hardware NMI enters bank $00 even with MEMSEL enabled. Switch only
    ; this native call to the identical FastROM mirror; DB remains zero for
    ; MMIO, and RTL restores the caller's bank before its saved frame.
    jsl $C00000+fast_video_entry
.else
    jsr native_video
.endif
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
.ifdef EXPERIMENTAL_FAST_PUBLISHER
fast_video_entry:
    .a8
    .i16
    jsr native_video
    rtl
.endif
.ifdef EXPERIMENTAL_TRANSITION_GAME_FIRST
video_publish_bridge:
    jsr publish_video
    rtl
.endif
audio_publish_bridge:
    ; One packet at original NMI exit, after that interrupt's sound update.
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
    lda $0A15
    pha
    APU_LENGTH_ENABLE
    sta $0A15
    jsr spc_frame
    pla
    sta $0A15
    bcc :+
    lda #$EE
    sta $1C0B
:
    lda #$00
    sta $0A16
.ifdef EXPERIMENTAL_SWEEP_EVENTS
    sta $0A14
.endif
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
.ifdef EXPERIMENTAL_RASTER
    pha
    lda $1C02
    sta $1CA6
    pla
    jml [$1CA4]
.else
    pha
    lda $4211
    pla
    ; Until the IRQ timing adapter is installed, CPU proof keeps IRQ disabled.
    rti
.endif
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
