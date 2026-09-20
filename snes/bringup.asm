; SNES hardware/audio diagnostic, NOT the River City Ransom game.
; All routines use DB=0, D=0, A8/X16 unless explicitly stated.
.setcpu "65816"
.macpack longbranch
.a8
.i16
.ifndef TRIANGLE_EDGE_OFFSET
TRIANGLE_EDGE_OFFSET = 0
.endif
.include "apu_length_gate.inc"
APU_PACKET = $0A00
.ifdef AUDIO_PULSE2
PULSE_PACKET = APU_PACKET+4
PULSE_BIT = 2
.else
PULSE_PACKET = APU_PACKET
.ifdef AUDIO_BOTH_PULSES
PULSE_BIT = 3
.else
PULSE_BIT = 1
.endif
.endif
.macro mirror_probe_pulses
.ifdef AUDIO_BOTH_PULSES
    .repeat 4, byte
        lda APU_PACKET+byte
        sta APU_PACKET+4+byte
    .endrepeat
.endif
.endmacro
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
    stz $0A25
.ifdef AUDIO_LENGTH_GATE
    lda #1                  ; initial pulse has a valid enabled reload
    sta $1CA1
.endif
    ldx #$0016
@clear:
    stz APU_PACKET,x
    dex
    bpl @clear
    jsr spc_upload
    jcs failed
.ifdef AUDIO_NOISE
    lda #$3F                 ; constant volume, length halt, long noise mode
    sta APU_PACKET+12
    lda #8
    sta APU_PACKET+$15
    sta APU_PACKET+$16
.elseif .defined(AUDIO_TRIANGLE)
    ; Isolated triangle: control/length halt set, linear reload nonzero.
    lda #$FF
    sta APU_PACKET+8
    lda #$FD
    sta APU_PACKET+10
    lda #4
    sta APU_PACKET+$15
    sta APU_PACKET+$16
.else
    ; Constant-volume square wave, NES timer $FD (~440 Hz NTSC).
    ; Loop/length-disable keeps this diagnostic independent of the host counters.
.ifdef AUDIO_LENGTH
    ; Same pulse, but length halt disabled and length index zero in $4003.
    ; The NES length counter must end this note without a $4015 mute write.
    lda #$9F
.else
    lda #$BF
.endif
.ifdef AUDIO_DUTY
    lda #$3F
.endif
    sta PULSE_PACKET
    lda #$FD
    sta PULSE_PACKET+2
    lda #PULSE_BIT
    sta APU_PACKET+$15
    lda #PULSE_BIT             ; selected pulse retrigger; mono output
    sta APU_PACKET+$16
.endif
    mirror_probe_pulses
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
.ifdef AUDIO_NOISE
    .include "noise_script.inc"
.elseif .defined(AUDIO_SCRIPT)
    rep #$20
    .a16
    lda FRAME
    cmp #120+TRIANGLE_EDGE_OFFSET
    beq @mute
    cmp #180+TRIANGLE_EDGE_OFFSET
    beq @restart
    cmp #240+TRIANGLE_EDGE_OFFSET
    beq @pitch
    sep #$20
    .a8
    bra @send_frame
@mute:
    sep #$20
    .a8
    stz APU_PACKET+$15
.ifdef AUDIO_DISABLED_RELOAD
.ifdef AUDIO_LENGTH_GATE
    ldx #$15
    jsr gate_write
.endif
    ; Model the existing packetizer's final bytes after $4015=0,
    ; $4003=0 (while disabled), $4015=1 before one publication.
    ; This is deliberately the collapsed packet, not an ordered NES replay.
    stz APU_PACKET+3
.ifdef AUDIO_LENGTH_GATE
    ldx #3
    jsr gate_write
.endif
    lda #$41
    sta APU_PACKET+$16
    lda #1
    sta APU_PACKET+$15
.ifdef AUDIO_LENGTH_GATE
    ldx #$15
    jsr gate_write
.endif
.endif
    lda #1
    sta PHASE
    bra @send_frame
@restart:
    sep #$20
    .a8
.ifdef AUDIO_TRIANGLE
    lda #4
.else
    lda #PULSE_BIT
.endif
    sta APU_PACKET+$15
.ifdef AUDIO_TRIANGLE
    lda #4
.else
    lda #PULSE_BIT
.endif
    sta APU_PACKET+$16
.ifdef AUDIO_LENGTH_GATE
    ldx #3
    jsr gate_write
.endif
    lda #2
    sta PHASE
    bra @send_frame
@pitch:
    sep #$20
    .a8
    lda #$7E
.ifdef AUDIO_TRIANGLE
    sta APU_PACKET+10
    lda #4
.else
    sta PULSE_PACKET+2
    lda #PULSE_BIT
.endif
    sta APU_PACKET+$16
    lda #3
    sta PHASE
@send_frame:
.endif
.ifdef AUDIO_SWEEP_RELOAD
    ; Keep writing/reloading the same pulse period while sweep is enabled.
    ; The period-reload flag is distinct from the note-start flag.
    lda #$F1
    sta APU_PACKET+1
.ifndef AUDIO_SWEEP_NO_RELOAD
    lda APU_PACKET+$16
    ora #$40
    sta APU_PACKET+$16
    inc $0A25
.endif
.endif
.ifdef AUDIO_RETRIGGER
    ; Periodic same-period high-register writes: retain the existing waveform
    ; and transport but exercise repeated note starts about twice per second.
    lda FRAME
    and #31
    bne :+
    lda #PULSE_BIT
    sta APU_PACKET+$16
    inc RETRIGGERS
:
.endif
.ifdef AUDIO_DUTY
    ; Duty-only changes: no timer, enable, volume or retrigger write here.
    lda FRAME
    and #32
    asl
    asl
    ora #$3F
    sta PULSE_PACKET
.endif
    mirror_probe_pulses
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
.include "native_spc_frame.inc"

interrupt:
    rti
.ifdef AUDIO_LENGTH_GATE
gate_write:
    APU_LENGTH_WRITE
    rts
.endif

.segment "RODATA"
audio_engine:
    .incbin "Memblers_2a03.bin"
audio_engine_end:
.ifdef AUDIO_TRIANGLE_RELEASE
    .assert audio_engine_end-audio_engine = $2C42, error, "Wrong diagnostic triangle-release SPC engine size"
.elseif .defined(AUDIO_TRIPLE)
.ifdef AUDIO_FAST_RESET
    .assert audio_engine_end-audio_engine = $2C7F, error, "Wrong triple fast-reset SPC engine size"
.else
    .assert audio_engine_end-audio_engine = $2C1F, error, "Wrong triple-port SPC engine size"
.endif
.elseif .defined(AUDIO_PAIR)
.ifdef AUDIO_RESET_NOTES
.ifdef AUDIO_FAST_RESET
    .assert audio_engine_end-audio_engine = $2C7F, error, "Wrong fast-reset SPC engine size"
.elseif .defined(AUDIO_DEFERRED_RESET)
    .assert audio_engine_end-audio_engine = $2C38, error, "Wrong deferred-reset SPC engine size"
.elseif .defined(AUDIO_SENTINEL_RESET)
    .assert audio_engine_end-audio_engine = $2C32, error, "Wrong sentinel-reset SPC engine size"
.else
    .assert audio_engine_end-audio_engine = $2C2F, error, "Wrong reset-note SPC engine size"
.endif
.else
.ifdef AUDIO_REUSE
    .assert audio_engine_end-audio_engine = $2C37, error, "Wrong packet-reuse SPC engine size"
.else
    .assert audio_engine_end-audio_engine = $2C1F, error, "Wrong paired SPC engine size"
.endif
.endif
.else
    .assert audio_engine_end-audio_engine = $2C00, error, "Wrong SPC engine size"
.endif

.segment "HEADER"
    .byte "RCR AUDIO BRINGUP    " ; 21-byte SNES title
    .byte $20, $00, $05, $00, $01, $00, $00
    .word $FFFF, $0000         ; finalized by tools/checksum.py
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
