; SNES hardware/audio diagnostic, NOT the River City Ransom game.
; All routines use DB=0, D=0, A8/X16 unless explicitly stated.
.setcpu "65816"
.macpack longbranch
.a8
.i16
APU_PACKET = $0A00
FRAME = $0A20
STATUS = $0A22                 ; 1=running, $EE=SPC timeout
PHASE = $0A23                  ; observable scripted-audio phase
RETRIGGERS = $0A24

.segment "CODE"
reset:
    sei
    clc
    xce
    rep #$38                  ; A/X16, clear decimal mode
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
    stz $420D
    stz $212C
    stz $212D
    stz $2130
    stz $2131
    stz $2133
    stz FRAME
    stz FRAME+1
    stz STATUS
    stz PHASE
    stz RETRIGGERS
    ldx #$0016
@clear:
    stz APU_PACKET,x
    dex
    bpl @clear
    jsr spc_upload
    jcs failed
    ; Constant-volume square wave, NES timer $FD (~440 Hz NTSC).
    ; Loop/length-disable keeps this diagnostic independent of the host counters.
.ifdef AUDIO_LENGTH
    ; Same pulse, but length halt disabled and length index zero in $4003.
    ; The NES length counter must end this note without a $4015 mute write.
    lda #$9F
.else
    lda #$BF
.endif
    sta APU_PACKET
    lda #$FD
    sta APU_PACKET+2
    lda #$01
    sta APU_PACKET+$15
    lda #$01                  ; square 0 retrigger; bit 5 clear for mono output
    sta APU_PACKET+$16
    jsr spc_frame
    jcs failed
    lda #$00
    sta APU_PACKET+$16
    lda #1
    sta STATUS
    ; Green backdrop signals successful handshake. This is diagnostic artwork only.
    stz $2121
    lda #$E0
    sta $2122
    lda #$03
    sta $2122
    lda #$0F
    sta $2100
@frame:
    ; Poll both edges: exactly one packet per VBlank, without installing game NMI.
    lda $4212
    bmi @frame
@vblank:
    lda $4212
    bpl @vblank
    inc FRAME
    bne :+
    inc FRAME+1
:
.ifdef AUDIO_SCRIPT
    rep #$20
    .a16
    lda FRAME
    cmp #120
    beq @mute
    cmp #180
    beq @restart
    cmp #240
    beq @pitch
    sep #$20
    .a8
    bra @send_frame
@mute:
    sep #$20
    .a8
    stz APU_PACKET+$15
    lda #1
    sta PHASE
    bra @send_frame
@restart:
    sep #$20
    .a8
    lda #1
    sta APU_PACKET+$15
    lda #$01
    sta APU_PACKET+$16
    lda #2
    sta PHASE
    bra @send_frame
@pitch:
    sep #$20
    .a8
    lda #$7E
    sta APU_PACKET+2
    lda #$01
    sta APU_PACKET+$16
    lda #3
    sta PHASE
@send_frame:
.endif
.ifdef AUDIO_RETRIGGER
    ; Periodic same-period high-register writes: retain the existing waveform
    ; and transport but exercise repeated note starts about twice per second.
    lda FRAME
    and #31
    bne :+
    lda #1
    sta APU_PACKET+$16
    inc RETRIGGERS
:
.endif
    jsr spc_frame
    bcs failed
    lda #$00
    sta APU_PACKET+$16
    jmp @frame
failed:
    lda #$EE
    sta STATUS
    stz $2121
    lda #$1F
    sta $2122
    stz $2122
    lda #$0F
    sta $2100
@halt:
    bra @halt

; Wait for A echoed on port 0, bounded by X. Carry marks timeout.
wait_port0:
    ldx #$FFFF
@poll:
    cmp $2140
    beq @ok
    dex
    bne @poll
    sec
    rts
@ok:
    clc
    rts

spc_upload:
    ldx #$FFFF
@ipl:
    lda $2140
    cmp #$AA
    bne @next
    lda $2141
    cmp #$BB
    beq @ready
@next:
    dex
    bne @ipl
    sec
    rts
@ready:
    ldx #$0400                ; entry/load address for this specific pinned engine
    stx $2142
    lda #1
    sta $2141
    lda #$CC
    sta $2140
    jsr wait_port0
    bcs @return
    ldy #0
@send:
    lda audio_engine,y
    sta $2141
    tya
    sta $2140
    jsr wait_port0
    bcs @return
    iny
    cpy #audio_engine_end-audio_engine
    bne @send
    stz $2141
    ldx #$0400
    stx $2142
    iny
    iny
    tya
    sta $2140
    lda #$7D
    jsr wait_port0
@return:
    rts

; Memblers/upernes legacy protocol. The newer Rumbleminze engine uses a
; DIFFERENT acknowledgement protocol; do not swap binaries without adapting it.
spc_frame:
    lda #$7D
    jsr wait_port0
    bcs @return
    lda #$D7
    sta $2140
    jsr wait_port0
    bcs @return
    ldy #0
    sty $2140                 ; APU ports 0,1=0 (X/Y are 16-bit)
@byte:
    lda APU_PACKET,y
    sta $2141
    tya
    jsr wait_port0
    bcs @return
    iny
    cpy #$17
    beq @done
    tya
    sta $2140
    bra @byte
@done:
    clc
@return:
    rts

interrupt:
    rti

.segment "RODATA"
audio_engine:
    .incbin "Memblers_2a03.bin"
audio_engine_end:
    .assert audio_engine_end-audio_engine = $2C00, error, "Wrong SPC engine size"

.segment "HEADER"
    .byte "RCR AUDIO BRINGUP    " ; 21-byte SNES title
    .byte $20, $00, $05, $00, $01, $00, $00
    .word $FFFF, $0000         ; finalized by tools/checksum.py
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
